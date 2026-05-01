"""Celery task: upload a rendered YouTube Long video to a YouTube channel."""
from __future__ import annotations

import logging

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="console.backend.tasks.youtube_upload_task.upload_youtube_video_task",
    queue="upload_q",
    max_retries=2,
    default_retry_delay=60,
)
def upload_youtube_video_task(self, youtube_video_id: int, channel_id: int):
    """Upload a rendered YouTube Long video to a YouTube channel."""
    from datetime import datetime, timezone

    from cryptography.fernet import Fernet

    from console.backend.config import settings
    from console.backend.database import SessionLocal
    from console.backend.models.channel import Channel
    from console.backend.models.credentials import PlatformCredential
    from console.backend.models.youtube_video import YoutubeVideo

    db = SessionLocal()
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            raise ValueError(f"YoutubeVideo {youtube_video_id} not found")
        if not video.output_path:
            raise ValueError(f"YoutubeVideo {youtube_video_id} has no output_path")

        channel = db.get(Channel, channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        cred = db.get(PlatformCredential, channel.credential_id)
        if not cred:
            raise ValueError(f"Credential not found for channel {channel_id}")

        fernet = Fernet(settings.FERNET_KEY.encode())

        def _decrypt(val: str | None) -> str | None:
            return fernet.decrypt(val.encode()).decode() if val else None

        credentials_dict = {
            "client_id":     cred.client_id,
            "client_secret": _decrypt(cred.client_secret),
            "access_token":  _decrypt(cred.access_token),
            "refresh_token": _decrypt(cred.refresh_token),
        }

        video_meta = {
            "title":          video.seo_title or video.title,
            "description":    video.seo_description or "",
            "tags":           video.seo_tags or [],
            "language":       channel.default_language or "en",
            "privacy_status": "unlisted",
        }

        from uploader.youtube_uploader import upload_to_youtube
        platform_id = upload_to_youtube(video.output_path, video_meta, credentials_dict)

        video.status = "published"
        video.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "YoutubeVideo %s uploaded to channel %s → platform_id=%s",
            youtube_video_id, channel_id, platform_id,
        )
        return {
            "youtube_video_id": youtube_video_id,
            "channel_id":       channel_id,
            "platform_id":      platform_id,
        }

    except Exception as exc:
        logger.exception(
            "Upload failed for YoutubeVideo %s to channel %s: %s",
            youtube_video_id, channel_id, exc,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
