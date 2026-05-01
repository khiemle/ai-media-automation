"""Celery task: orchestrate full YouTube long-form video rendering."""
from __future__ import annotations

import logging
import os
import time
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
    """Render a long-form landscape YouTube video."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers FK target
    from pipeline.youtube_ffmpeg import render_landscape

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
        output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}_v{int(time.time())}.mp4"

        render_landscape(video, output_path, db)
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
