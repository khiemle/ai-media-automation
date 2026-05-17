"""Celery task: upload a rendered YouTube video to a YouTube channel."""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


_YOUR_CHANNEL_PLACEHOLDER_RE = re.compile(r"\[[^\]]*your channel[^\]]*\]", re.IGNORECASE)


def substitute_channel_placeholders(description: str | None, channel_url: str | None) -> str:
    """Replace bracketed 'your channel' placeholders with the channel URL.

    LLM-generated SEO descriptions often include instructions like
    "[Add links to other work ambience videos in your channel here]" that
    expect the editor to insert a channel link. When a channel.channel_url
    is configured, we substitute these placeholders automatically at upload
    time. If channel_url is unset, the placeholder stays so the editor can
    notice and fill it in.
    """
    if not description:
        return description or ""
    if not channel_url:
        return description
    return _YOUR_CHANNEL_PLACEHOLDER_RE.sub(channel_url, description)

from console.backend.celery_app import celery_app
from console.backend.config import settings
from console.backend.database import SessionLocal
from console.backend.models.channel import Channel
from console.backend.models.credentials import PlatformCredential
from console.backend.models.video_asset import VideoAsset  # noqa: F401 — registers video_assets FK target
from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers video_templates FK target
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload
from uploader.youtube_uploader import set_thumbnail, upload as _youtube_upload

logger = logging.getLogger(__name__)

_COMPRESS_THRESHOLD_GB = 12  # re-encode if file exceeds this before uploading
_UPLOAD_MAXRATE = "8M"
_UPLOAD_BUFSIZE = "16M"


def _compress_for_upload(src: Path) -> Path:
    """Re-encode a large MP4 at 8 Mbps max so the upload is manageable.

    Outputs a sibling file named <stem>_compressed.mp4.  Audio is stream-copied
    to avoid a second decode/encode pass.
    """
    dst = src.with_name(src.stem + "_compressed.mp4")
    logger.info("[YouTube] Compressing %s (%.1f GB) → %s", src, src.stat().st_size / 1e9, dst)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", "libx264", "-preset", "faster", "-crf", "23",
        "-maxrate", _UPLOAD_MAXRATE, "-bufsize", _UPLOAD_BUFSIZE,
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=7200)
    if result.returncode != 0:
        raise RuntimeError(f"Compression failed: {(result.stderr or b'')[-600:].decode()}")
    logger.info("[YouTube] Compressed to %.1f GB", dst.stat().st_size / 1e9)
    return dst


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

        template = db.get(VideoTemplate, video.template_id) if video.template_id else None
        description = substitute_channel_placeholders(
            video.seo_description or "", channel.channel_url
        )
        video_meta = {
            "title":          video.seo_title or video.title,
            "description":    description,
            "tags":           video.seo_tags or [],
            "language":       channel.default_language or "en",
            "privacy_status": "unlisted",
            "output_format":  template.output_format if template else None,
        }

        from console.backend.services.youtube_video_service import YoutubeVideoService
        chapters = YoutubeVideoService(db).build_chapters(video)

        upload_path = Path(video.output_path)
        size_gb = upload_path.stat().st_size / 1e9
        if size_gb > _COMPRESS_THRESHOLD_GB:
            logger.info(
                "[YouTube] File is %.1f GB (> %s GB threshold) — compressing before upload",
                size_gb, _COMPRESS_THRESHOLD_GB,
            )
            upload_path = _compress_for_upload(upload_path)

        platform_id = _youtube_upload(str(upload_path), video_meta, credentials_dict, chapters=chapters)

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
