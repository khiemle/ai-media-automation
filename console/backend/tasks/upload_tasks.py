import logging
from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="console.backend.tasks.upload_tasks.upload_to_channel_task", queue="upload_q")
def upload_to_channel_task(self, video_id: str, channel_id: int):
    """Upload a rendered video to a specific channel."""
    from console.backend.database import SessionLocal
    from console.backend.models.channel import Channel, UploadTarget
    from console.backend.models.credentials import PlatformCredential
    from cryptography.fernet import Fernet
    from console.backend.config import settings

    self.update_state(state="PROGRESS", meta={"step": "uploading", "channel_id": channel_id})
    db = SessionLocal()
    try:
        target = db.query(UploadTarget).filter(
            UploadTarget.video_id == video_id,
            UploadTarget.channel_id == channel_id,
        ).first()
        if not target:
            raise ValueError(f"Upload target not found: video={video_id}, channel={channel_id}")

        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        cred = db.query(PlatformCredential).filter(PlatformCredential.id == channel.credential_id).first()

        # Decrypt tokens
        fernet = Fernet(settings.FERNET_KEY.encode())
        access_token = fernet.decrypt(cred.access_token.encode()).decode() if cred.access_token else None
        refresh_token = fernet.decrypt(cred.refresh_token.encode()).decode() if cred.refresh_token else None

        credentials_dict = {
            "client_id": cred.client_id,
            "client_secret": fernet.decrypt(cred.client_secret.encode()).decode() if cred.client_secret else None,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

        # Fetch video metadata from the script
        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == video_id).first()
        video_meta = script.script_json.get("video", {}) if script else {}
        video_path = script.output_path if script and hasattr(script, "output_path") else None

        target.status = "uploading"
        db.commit()

        # Dispatch to the right uploader
        platform_id = None
        if channel.platform == "youtube":
            from uploader.youtube_uploader import upload_to_youtube
            platform_id = upload_to_youtube(video_path, video_meta, credentials_dict)
        elif channel.platform == "tiktok":
            from uploader.tiktok_uploader import upload_to_tiktok
            platform_id = upload_to_tiktok(video_path, video_meta, credentials_dict)

        from datetime import datetime, timezone
        target.status = "published"
        target.uploaded_at = datetime.now(timezone.utc)
        target.platform_id = platform_id
        db.commit()

        logger.info(f"Upload complete: video={video_id} → channel={channel_id} ({platform_id})")
        return {"video_id": video_id, "channel_id": channel_id, "platform_id": platform_id}
    except Exception as e:
        db.rollback()
        target = db.query(UploadTarget).filter(
            UploadTarget.video_id == video_id,
            UploadTarget.channel_id == channel_id,
        ).first()
        if target:
            target.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
