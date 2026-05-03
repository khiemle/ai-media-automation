"""Unified render-state reader for YouTube videos."""
from sqlalchemy.orm import Session

from console.backend.models.youtube_video import YoutubeVideo


def get_render_state(db: Session, video_id: int) -> dict:
    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise KeyError(f"YoutubeVideo {video_id} not found")

    parts = list(video.render_parts or [])
    completed = sum(1 for p in parts if p.get("status") == "completed")
    failed    = sum(1 for p in parts if p.get("status") == "failed")
    running   = sum(1 for p in parts if p.get("status") == "running")
    pending   = sum(1 for p in parts if p.get("status") == "pending")

    overall = int(100 * completed / len(parts)) if parts else 0

    return {
        "video_id": video_id,
        "status": video.status,
        "audio_preview_path": video.audio_preview_path,
        "video_preview_path": video.video_preview_path,
        "output_path": video.output_path,
        "chunks": [
            {
                "idx": p.get("idx"),
                "start_s": p.get("start_s"),
                "end_s": p.get("end_s"),
                "status": p.get("status"),
                "error": p.get("error"),
            }
            for p in sorted(parts, key=lambda p: p.get("idx", 0))
        ],
        "chunk_summary": {
            "total": len(parts),
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
        },
        "overall_progress": overall,
        "celery_task_id": video.celery_task_id,
    }
