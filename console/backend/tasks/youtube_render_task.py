"""Celery task: orchestrate full YouTube long-form video rendering."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.environ.get("RENDER_OUTPUT_PATH", "./renders/youtube"))

_QUALITY_SCALE = {
    "4K":    "3840:2160",
    "1080p": "1920:1080",
}
_DEFAULT_SCALE = "1920:1080"

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_video",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_video_task(self, youtube_video_id: int):
    """Orchestrate rendering of a long-form YouTube video."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers FK target in SA metadata

    db = SessionLocal()
    video = None
    render_completed = False
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        if video.status not in {"draft", "queued"}:
            logger.warning(
                "YoutubeVideo %s is already %s; skipping render",
                youtube_video_id, video.status,
            )
            return {"status": "skipped", "reason": f"already {video.status}"}

        video.status = "rendering"
        db.commit()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        import time as _time
        output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}_v{int(_time.time())}.mp4"

        _render_video(video, output_path, db)
        render_completed = True

        video.status = "done"
        video.output_path = str(output_path)
        db.commit()

        logger.info("YoutubeVideo %s rendered to %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s render failed: %s", youtube_video_id, exc)
        if video is not None and not render_completed:
            try:
                video.status = "failed"
                db.commit()
            except Exception as db_exc:
                db.rollback()
                logger.error(
                    "Failed to persist 'failed' status for YoutubeVideo %s: %s",
                    youtube_video_id, db_exc,
                )
        raise self.retry(exc=exc)
    finally:
        db.close()


def _render_video(video, output_path: Path, db) -> None:
    """Compose the YouTube video using visual asset, music track, and SFX layers."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    scale = _QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", _DEFAULT_SCALE)
    w, h = scale.split(":")

    visual_path = _resolve_visual(video, db)
    music_path = _resolve_audio(video, db)
    sfx_layers = _resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in _IMAGE_EXTS

    # Collect all audio inputs: music first, then SFX layers
    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    cmd = ["ffmpeg", "-y"]

    # Video input (index 0)
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # Audio inputs (indices 1+)
    if audio_inputs:
        for (path, _) in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]

        # Build filter_complex: per-input volume + video vf (must be in filter_complex when -map is used)
        parts: list[str] = []
        audio_labels: list[str] = []
        for i, (_, vol) in enumerate(audio_inputs):
            parts.append(f"[{i + 1}:a]volume={vol}[a{i}]")
            audio_labels.append(f"[a{i}]")

        parts.append(f"[0:v]{vf}[vout]")

        if len(audio_inputs) == 1:
            filter_complex = ";".join(parts)
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[a0]",
            ]
        else:
            mix_in = "".join(audio_labels)
            parts.append(
                f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
            )
            cmd += [
                "-filter_complex", ";".join(parts),
                "-map", "[vout]",
                "-map", "[aout]",
            ]
    else:
        # No audio — silence fallback, use simple -vf (no explicit -map needed)
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf]

    # Duration
    cmd += ["-t", str(duration_s)]

    # Codec
    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += [
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("ffmpeg render cmd: %s", " ".join(cmd))

    timeout = max(duration_s * 4, 600)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s")

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(result.stderr or '')[-800:]}")


def _resolve_visual(video, db) -> str | None:
    """Return the file path of the linked visual asset, or None."""
    if not video.visual_asset_id:
        return None
    try:
        from console.backend.models.video_asset import VideoAsset
        asset = db.get(VideoAsset, video.visual_asset_id)
        if asset and asset.file_path:
            return asset.file_path
    except Exception as exc:
        logger.warning("Could not load visual asset %s: %s", video.visual_asset_id, exc)
    return None


def _resolve_audio(video, db) -> str | None:
    """Return the file path of the linked music track, or None."""
    if not video.music_track_id:
        return None
    try:
        from database.models import MusicTrack
        track = db.get(MusicTrack, video.music_track_id)
        if track and track.file_path:
            return track.file_path
    except Exception as exc:
        logger.warning("Could not load music track %s: %s", video.music_track_id, exc)
    return None


def _resolve_sfx_layers(video, db) -> list[tuple[str, float]]:
    """Resolve SFX layer file paths from video.sfx_overrides."""
    overrides = video.sfx_overrides
    if not overrides:
        return []

    results = []
    for layer_name in ("foreground", "midground", "background"):
        layer = overrides.get(layer_name)
        if not layer:
            continue
        asset_id = layer.get("asset_id")
        volume = float(layer.get("volume", 0.5))
        if not asset_id:
            continue
        try:
            from console.backend.models.sfx_asset import SfxAsset
            asset = db.get(SfxAsset, int(asset_id))
            if asset and asset.file_path and Path(asset.file_path).is_file():
                results.append((asset.file_path, volume))
            else:
                logger.warning("SFX asset %s not found or missing file on disk", asset_id)
        except Exception as exc:
            logger.warning("Could not resolve SFX asset %s: %s", asset_id, exc)

    return results
