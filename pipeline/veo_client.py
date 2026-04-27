"""
Google Veo video generation client.
Generates 8s portrait clips; chains multiple clips for longer scenes.
Each segment is stored individually in the Asset DB for future reuse.
"""
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

from config.api_config import get_config

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

ASSET_DB_PATH    = os.environ.get("ASSET_DB_PATH", "./assets/video_db")
VEO_TIMEOUT      = 300  # seconds per segment
VEO_POLL_INTERVAL = 5   # seconds between status checks

TARGET_W, TARGET_H = 1080, 1920


class VeoClient:
    def __init__(self):
        cfg = get_config()
        key = cfg["gemini"]["media"]["api_key"]
        self._model = cfg["gemini"]["media"]["model"]
        if not key:
            raise RuntimeError("Gemini media API key is not configured in config/api_keys.json")
        try:
            from google import genai
            from google.genai import types as genai_types
            self._client = genai.Client(api_key=key)
            self._genai_types = genai_types
        except ImportError:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

    def generate_segment(self, prompt: str, scene_id: str, seg_idx: int) -> Path | None:
        """Generate one 8s video segment using Veo API. Returns local file path."""
        client      = self._client
        genai_types = self._genai_types

        try:
            op = client.models.generate_videos(
                model=self._model,
                prompt=prompt,
                config=genai_types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    duration_seconds=8,
                    number_of_videos=1,
                    resolution="1080p",
                    person_generation="allow_adult",
                ),
            )

            # Poll until complete
            start = time.time()
            while not op.done:
                time.sleep(VEO_POLL_INTERVAL)
                op = client.operations.get(name=op.name)
                elapsed = time.time() - start
                if elapsed > VEO_TIMEOUT:
                    raise TimeoutError(f"Veo timeout after {VEO_TIMEOUT}s for scene={scene_id} seg={seg_idx}")
                logger.debug(f"[Veo] Waiting for {scene_id}_{seg_idx} ({elapsed:.0f}s elapsed)")

            # Download the generated video
            out_dir = Path(ASSET_DB_PATH) / "veo"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{scene_id}_seg{seg_idx}.mp4"

            video = op.response.generated_videos[0].video
            video.save(str(out_path))
            logger.info(f"[Veo] Generated segment: {out_path}")
            return out_path

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[Veo] Segment generation failed scene={scene_id} seg={seg_idx}: {e}")
            return None

    def generate_for_scene(
        self,
        scene: dict,
        meta: dict,
        scene_id: str,
        keywords: list[str],
        niche: str,
    ) -> Path | None:
        """
        Generate video clip(s) for a scene, chain if duration > 8s,
        write-back each segment to the Asset DB.
        Returns path to final clip (trimmed to scene duration).
        """
        from pipeline.veo_prompt_builder import build_veo_prompt, clips_needed

        duration = float(scene.get("duration", 8))
        n_clips  = clips_needed(duration)
        prompt   = build_veo_prompt(scene, meta)

        segments: list[Path] = []
        for i in range(n_clips):
            seg_path = self.generate_segment(prompt, scene_id, i)
            if seg_path is None:
                logger.warning(f"[Veo] Segment {i} failed, trying Pexels fallback")
                return self._pexels_fallback(keywords, niche, duration, scene_id)

            # Resize segment to portrait
            resized = self._resize(seg_path, scene_id, i)
            if resized:
                segments.append(resized)
                # Write each 8s segment to Asset DB for future reuse
                try:
                    from pipeline.asset_db import write as write_asset
                    write_asset(
                        file_path=str(resized),
                        source="veo",
                        keywords=keywords,
                        niche=niche,
                        veo_prompt=prompt,
                        quality_score=0.85,
                    )
                except Exception as e:
                    logger.warning(f"[Veo] Asset DB write failed: {e}")

        if not segments:
            return None

        if len(segments) == 1:
            return self._trim(segments[0], duration, scene_id)

        # Concatenate multiple segments
        concat_path = Path(ASSET_DB_PATH) / "veo" / f"{scene_id}_concat.mp4"
        self._concat(segments, concat_path)
        return self._trim(concat_path, duration, scene_id)

    def _resize(self, src: Path, scene_id: str, seg_idx: int) -> Path | None:
        """Center-crop to 1080×1920 portrait."""
        dst = src.parent / f"{src.stem}_portrait.mp4"
        vf  = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},fps=30"
        )
        cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20", str(dst)]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            return dst
        except Exception as e:
            logger.error(f"[Veo] resize failed: {e}")
            return src  # return original if resize fails

    def _trim(self, src: Path, duration: float, scene_id: str) -> Path:
        """Trim to exact scene duration."""
        dst = src.parent / f"{scene_id}_final.mp4"
        cmd = ["ffmpeg", "-y", "-i", str(src), "-t", str(duration), "-c", "copy", str(dst)]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            return dst
        except Exception:
            return src

    def _concat(self, segments: list[Path], dst: Path):
        """Concatenate multiple video segments using ffmpeg concat demuxer."""
        list_file = Path(tempfile.mktemp(suffix=".txt"))
        list_file.write_text("\n".join(f"file '{s}'" for s in segments))
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(dst)]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        except Exception as e:
            logger.error(f"[Veo] concat failed: {e}")
        finally:
            list_file.unlink(missing_ok=True)

    def _pexels_fallback(self, keywords: list[str], niche: str, duration: float, scene_id: str) -> Path | None:
        """Fall back to Pexels when Veo fails."""
        try:
            from pipeline.pexels_client import search_and_download
            logger.info(f"[Veo] Falling back to Pexels for scene {scene_id}")
            return search_and_download(keywords, niche, duration, scene_id)
        except Exception as e:
            logger.error(f"[Veo] Pexels fallback also failed: {e}")
            return None


_client: VeoClient | None = None


def get_client() -> VeoClient:
    global _client
    if _client is None:
        _client = VeoClient()
    return _client
