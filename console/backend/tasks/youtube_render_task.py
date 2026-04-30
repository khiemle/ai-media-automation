"""Celery task: orchestrate full YouTube long-form video rendering."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.environ.get("RENDER_OUTPUT_PATH", "./renders/youtube"))


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

    db = SessionLocal()
    video = None
    render_completed = False
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        # Guard: skip if already rendering or done (prevents concurrent corruption)
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

        _render_placeholder(video, output_path)
        render_completed = True

        video.status = "done"
        video.output_path = str(output_path)
        db.commit()

        logger.info("YoutubeVideo %s rendered to %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s render failed: %s", youtube_video_id, exc)
        if video is not None and not render_completed:
            # Only mark failed if render itself didn't complete
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


def _render_placeholder(video, output_path: Path) -> None:
    """Placeholder render: creates a minimal valid .mp4 using ffmpeg lavfi."""
    import shutil
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH — install ffmpeg to render videos")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    duration_s = min(duration_s, 60)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=30:d={duration_s}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300, text=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timeout after 300s rendering {output_path}")

    if result.returncode != 0:
        stderr_msg = (result.stderr or "<no stderr>")[:500]
        raise RuntimeError(f"ffmpeg placeholder render failed: {stderr_msg}")
