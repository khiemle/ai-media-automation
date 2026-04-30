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
    """Compose the YouTube video using the linked visual asset and music track."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    scale = _QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", _DEFAULT_SCALE)
    w, h = scale.split(":")

    visual_path = _resolve_visual(video, db)
    audio_path = _resolve_audio(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in _IMAGE_EXTS

    cmd = ["ffmpeg", "-y"]

    # ── Video input ───────────────────────────────────────────────────────────
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        # Fallback: solid black background
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # ── Audio input ───────────────────────────────────────────────────────────
    if audio_path and Path(audio_path).is_file():
        cmd += ["-stream_loop", "-1", "-i", audio_path]
    else:
        # Fallback: silence
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

    # ── Duration + filters ────────────────────────────────────────────────────
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"

    cmd += [
        "-t", str(duration_s),
        "-vf", vf,
    ]

    # ── Codec settings ────────────────────────────────────────────────────────
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

    timeout = max(duration_s * 4, 600)  # at least 10 min; allow ~4× realtime for slow machines
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
