"""
Pexels stock footage client.
Searches portrait videos, downloads, trims, and resizes to 1080×1920.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)

import httpx

logger = logging.getLogger(__name__)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
ASSET_DB_PATH  = os.environ.get("ASSET_DB_PATH", "./assets/video_db")
PEXELS_BASE    = "https://api.pexels.com/videos"

TARGET_W, TARGET_H = 1080, 1920
TARGET_FPS         = 30


def search_and_download(
    keywords:     list[str],
    niche:        str,
    min_duration: float,
    scene_id:     str = "scene",
) -> Path | None:
    """
    Search Pexels for a portrait video matching keywords,
    download, trim, and resize to 1080×1920.
    Returns clip path or None on failure.
    """
    if not PEXELS_API_KEY:
        logger.warning("[Pexels] PEXELS_API_KEY not set — skipping")
        return None

    query = " ".join(keywords[:4])
    video_data = _search(query, min_duration)
    if not video_data:
        # Fallback: try niche as query
        video_data = _search(niche, min_duration)
    if not video_data:
        logger.warning(f"[Pexels] No results for query='{query}'")
        return None

    raw_path = _download(video_data, scene_id)
    if not raw_path:
        return None

    out_path = Path(ASSET_DB_PATH) / "pexels" / f"{raw_path.stem}_final.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    clipped = _trim_and_resize(raw_path, out_path, min_duration)
    if clipped and clipped.exists():
        raw_path.unlink(missing_ok=True)
        # Write to asset DB
        try:
            from pipeline.asset_db import write as write_asset
            write_asset(
                file_path=str(clipped),
                source="pexels",
                keywords=keywords,
                niche=niche,
                source_id=str(video_data.get("id", "")),
                quality_score=0.75,
            )
        except Exception as e:
            logger.warning(f"[Pexels] Asset DB write failed: {e}")
        return clipped

    return None


def _search(query: str, min_duration: float) -> dict | None:
    """Call Pexels video search API and return the best matching video."""
    try:
        resp = httpx.get(
            f"{PEXELS_BASE}/search",
            params={
                "query":       query,
                "orientation": "portrait",
                "size":        "large",
                "per_page":    10,
            },
            headers={"Authorization": PEXELS_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

        # Pick first with sufficient duration at best quality
        for v in videos:
            if v.get("duration", 0) >= min_duration:
                return v

        # Relax duration constraint: take any video (will loop)
        return videos[0] if videos else None
    except Exception as e:
        logger.error(f"[Pexels] search error: {e}")
        return None


def _download(video_data: dict, scene_id: str) -> Path | None:
    """Download the highest quality video file from Pexels."""
    files = sorted(
        video_data.get("video_files", []),
        key=lambda f: f.get("width", 0) * f.get("height", 0),
        reverse=True,
    )
    if not files:
        return None

    url  = files[0]["link"]
    dest = Path(tempfile.mkdtemp()) / f"pexels_{scene_id}_{video_data['id']}.mp4"

    try:
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"[Pexels] Downloaded {dest.name} ({dest.stat().st_size // 1024}KB)")
        return dest
    except Exception as e:
        logger.error(f"[Pexels] download failed: {e}")
        return None


def _trim_and_resize(src: Path, dst: Path, duration: float) -> Path | None:
    """Trim to duration and resize+crop to 1080×1920 portrait using ffmpeg."""
    # Scale to fill 1080×1920, center crop
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"fps={TARGET_FPS}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-t", str(duration),
        "-vf", vf,
        "-an",                  # no audio — narration added by composer
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        str(dst),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return dst
    except subprocess.CalledProcessError as e:
        logger.error(f"[Pexels] ffmpeg resize failed: {e.stderr.decode()[-300:]}")
        return None
