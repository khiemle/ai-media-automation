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
    name="console.backend.tasks.youtube_render_task.render_youtube_video",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_video_task(self, youtube_video_id: int):
    """
    Orchestrate rendering of a long-form YouTube video.

    Steps:
    1. Load YoutubeVideo + VideoTemplate from DB
    2. Update status → "rendering"
    3. Resolve/assemble audio (music track + SFX mix)  [placeholder]
    4. Resolve/assemble visual segments (scene assets)  [placeholder]
    5. Render final video with ffmpeg (concatenate segments with audio)
    6. Update status → "done", output_path set
    7. On failure → status → "failed", re-raise for retry

    Steps 3-4 are stubs that will be wired to real pipeline modules in a
    future task (pipeline integration sprint).
    """
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo

    db = SessionLocal()
    video = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        # Step 2: Mark rendering
        video.status = "rendering"
        db.commit()
        logger.info("YoutubeVideo %s → rendering", youtube_video_id)

        # Steps 3-5: Placeholder — real asset assembly wired in future task
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}.mp4"

        _render_placeholder(video, output_path)

        # Step 6: Mark done
        video.status = "done"
        video.output_path = str(output_path)
        db.commit()

        logger.info("YoutubeVideo %s rendered → %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s render failed: %s", youtube_video_id, exc)
        if video is not None:
            try:
                video.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


def _render_placeholder(video, output_path: Path) -> None:
    """
    Placeholder render: creates a minimal valid .mp4 using ffmpeg lavfi sources.
    Will be replaced by real asset assembly + ffmpeg compose in pipeline integration.
    """
    # target_duration_h is stored in hours; convert to seconds, default 3 h
    duration_s = int((video.target_duration_h or 3.0) * 3600)
    # Cap at 60 s for placeholder renders to avoid huge files during development
    duration_s = min(duration_s, 60)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=30:d={duration_s}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg placeholder render failed: {result.stderr.decode()[:500]}"
        )
