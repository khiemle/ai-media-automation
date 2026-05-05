"""Celery task: upload a rendered YouTube video to a YouTube channel."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from console.backend.celery_app import celery_app
from console.backend.config import settings
from console.backend.database import SessionLocal
from console.backend.models.channel import Channel
from console.backend.models.credentials import PlatformCredential
from console.backend.models.video_asset import VideoAsset  # noqa: F401 — registers video_assets FK target
from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers video_templates FK target
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload
from uploader.youtube_uploader import set_thumbnail, upload_to_youtube

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="console.backend.tasks.youtube_upload_task.upload_youtube_video_task",
    queue="upload_q",
    max_retries=2,
    default_retry_delay=60,
)
def upload_youtube_video_task(self, youtube_video_id: int, channel_id: int, upload_id: int):
    """Upload a rendered YouTube video to a channel; track status on YoutubeVideoUpload."""
    db = SessionLocal()
    upload = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            raise ValueError(f"YoutubeVideo {youtube_video_id} not found")
        if not video.output_path:
            raise ValueError(f"YoutubeVideo {youtube_video_id} has no output_path")

        upload = db.get(YoutubeVideoUpload, upload_id)
        if not upload:
            raise ValueError(f"YoutubeVideoUpload {upload_id} not found")

        channel = db.get(Channel, channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        cred = db.get(PlatformCredential, channel.credential_id)
        if not cred:
            raise ValueError(f"Credential not found for channel {channel_id}")

        # Mark uploading
        upload.status = "uploading"
        db.commit()

        def _decrypt(val: str | None) -> str | None:
            return Fernet(settings.FERNET_KEY.encode()).decrypt(val.encode()).decode() if val else None

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

        platform_id = upload_to_youtube(video.output_path, video_meta, credentials_dict)

        if video.thumbnail_path:
            try:
                set_thumbnail(platform_id, video.thumbnail_path, credentials_dict)
            except Exception as thumb_exc:
                logger.warning(
                    "Thumbnail set failed for YoutubeVideo %s → %s: %s",
                    youtube_video_id, platform_id, thumb_exc,
                )

        upload.status = "done"
        upload.platform_id = platform_id
        upload.uploaded_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "YoutubeVideo %s uploaded to channel %s → platform_id=%s",
            youtube_video_id, channel_id, platform_id,
        )
        return {
            "youtube_video_id": youtube_video_id,
            "channel_id":       channel_id,
            "upload_id":        upload_id,
            "platform_id":      platform_id,
        }

    except Exception as exc:
        logger.exception(
            "Upload failed for YoutubeVideo %s to channel %s: %s",
            youtube_video_id, channel_id, exc,
        )
        if upload is not None:
            try:
                upload.status = "failed"
                upload.error = str(exc)
                db.commit()
            except Exception:
                db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
