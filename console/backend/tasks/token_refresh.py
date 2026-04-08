import logging
from datetime import datetime, timedelta, timezone

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="console.backend.tasks.token_refresh.refresh_expiring_tokens")
def refresh_expiring_tokens():
    """Refresh OAuth tokens expiring within the next hour."""
    from console.backend.database import SessionLocal
    from console.backend.models.credentials import PlatformCredential
    from cryptography.fernet import Fernet
    from console.backend.config import settings
    import httpx

    db = SessionLocal()
    refreshed = 0
    errors = 0

    try:
        soon = datetime.now(timezone.utc) + timedelta(hours=1)
        expiring = (
            db.query(PlatformCredential)
            .filter(
                PlatformCredential.status == "connected",
                PlatformCredential.token_expires_at <= soon,
                PlatformCredential.refresh_token.isnot(None),
            )
            .all()
        )

        fernet = Fernet(settings.FERNET_KEY.encode())

        for cred in expiring:
            try:
                refresh_token = fernet.decrypt(cred.refresh_token.encode()).decode()
                client_secret = fernet.decrypt(cred.client_secret.encode()).decode() if cred.client_secret else None

                resp = httpx.post(
                    cred.token_endpoint,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": cred.client_id,
                        "client_secret": client_secret,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

                cred.access_token = fernet.encrypt(data["access_token"].encode()).decode()
                if "refresh_token" in data:
                    cred.refresh_token = fernet.encrypt(data["refresh_token"].encode()).decode()
                expires_in = data.get("expires_in", 3600)
                cred.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                cred.last_refreshed = datetime.now(timezone.utc)
                cred.status = "connected"
                refreshed += 1
                logger.info(f"Refreshed token for credential {cred.id} ({cred.platform})")
            except Exception as e:
                cred.status = "expired"
                errors += 1
                logger.error(f"Failed to refresh token for credential {cred.id}: {e}")

        db.commit()
    finally:
        db.close()

    return {"refreshed": refreshed, "errors": errors}
