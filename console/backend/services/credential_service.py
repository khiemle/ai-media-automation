"""CredentialService — Fernet encrypt/decrypt, OAuth URL, token refresh, connection test."""
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from console.backend.config import settings
from console.backend.models.credentials import PlatformCredential

logger = logging.getLogger(__name__)

PLATFORM_DEFAULTS = {
    "youtube": {
        "auth_endpoint":  "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
    },
    "tiktok": {
        "auth_endpoint":  "https://www.tiktok.com/auth/authorize/",
        "token_endpoint": "https://open-api.tiktok.com/oauth/access_token/",
        "scopes": ["user.info.basic", "video.upload"],
    },
    "instagram": {
        "auth_endpoint":  "https://api.instagram.com/oauth/authorize",
        "token_endpoint": "https://api.instagram.com/oauth/access_token",
        "scopes": ["basic", "publish_media"],
    },
}


def _fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


class CredentialService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def list_credentials(self) -> list[dict]:
        creds = self.db.query(PlatformCredential).order_by(PlatformCredential.platform).all()
        return [self._safe_dict(c) for c in creds]

    def get_credential(self, cred_id: int) -> dict:
        cred = self._get_or_404(cred_id)
        return self._safe_dict(cred)

    def upsert_credential(self, platform: str, data: dict) -> dict:
        """Create or update credential config. Encrypts secrets before storing."""
        cred = self.db.query(PlatformCredential).filter(
            PlatformCredential.platform == platform
        ).first()

        if not cred:
            defaults = PLATFORM_DEFAULTS.get(platform, {})
            cred = PlatformCredential(
                platform=platform,
                name=data.get("name", platform.title()),
                auth_endpoint=defaults.get("auth_endpoint"),
                token_endpoint=defaults.get("token_endpoint"),
                scopes=defaults.get("scopes", []),
                status="disconnected",
            )
            self.db.add(cred)

        cred.name = data.get("name", cred.name)
        cred.client_id = data.get("client_id", cred.client_id)
        cred.redirect_uri = data.get("redirect_uri", cred.redirect_uri)

        if "client_secret" in data and data["client_secret"]:
            cred.client_secret = encrypt(data["client_secret"])

        if "auth_endpoint" in data:
            cred.auth_endpoint = data["auth_endpoint"]
        if "token_endpoint" in data:
            cred.token_endpoint = data["token_endpoint"]
        if "scopes" in data:
            cred.scopes = data["scopes"]

        cred.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(cred)
        return self._safe_dict(cred)

    # ── OAuth URL builder ─────────────────────────────────────────────────────

    def build_oauth_url(self, platform: str, state: str | None = None) -> str:
        cred = self.db.query(PlatformCredential).filter(
            PlatformCredential.platform == platform
        ).first()
        if not cred or not cred.client_id or not cred.auth_endpoint:
            raise ValueError(f"Credential for '{platform}' is not configured")

        params = {
            "client_id":     cred.client_id,
            "redirect_uri":  cred.redirect_uri or "",
            "response_type": "code",
            "scope":         " ".join(cred.scopes or []),
            "access_type":   "offline",
        }
        if state:
            params["state"] = state

        return f"{cred.auth_endpoint}?{urlencode(params)}"

    # ── OAuth callback ─────────────────────────────────────────────────────────

    def exchange_code(self, platform: str, code: str) -> dict:
        """Exchange authorization code for tokens and store encrypted."""
        cred = self.db.query(PlatformCredential).filter(
            PlatformCredential.platform == platform
        ).first()
        if not cred or not cred.token_endpoint:
            raise ValueError(f"Credential for '{platform}' not configured")

        client_secret = decrypt(cred.client_secret) if cred.client_secret else ""
        resp = httpx.post(
            cred.token_endpoint,
            data={
                "code":          code,
                "client_id":     cred.client_id,
                "client_secret": client_secret,
                "redirect_uri":  cred.redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()

        cred.access_token = encrypt(tokens["access_token"])
        if "refresh_token" in tokens:
            cred.refresh_token = encrypt(tokens["refresh_token"])
        expires_in = tokens.get("expires_in", 3600)
        cred.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        cred.last_refreshed = datetime.now(timezone.utc)
        cred.status = "connected"
        cred.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        return self._safe_dict(cred)

    # ── Token refresh ─────────────────────────────────────────────────────────

    def refresh_token(self, cred_id: int) -> dict:
        cred = self._get_or_404(cred_id)
        if not cred.refresh_token:
            raise ValueError("No refresh token stored")

        refresh_token = decrypt(cred.refresh_token)
        client_secret = decrypt(cred.client_secret) if cred.client_secret else ""

        resp = httpx.post(
            cred.token_endpoint,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     cred.client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        tokens = resp.json()

        cred.access_token = encrypt(tokens["access_token"])
        if "refresh_token" in tokens:
            cred.refresh_token = encrypt(tokens["refresh_token"])
        expires_in = tokens.get("expires_in", 3600)
        cred.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        cred.last_refreshed = datetime.now(timezone.utc)
        cred.status = "connected"
        cred.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        return self._safe_dict(cred)

    # ── Connection test ───────────────────────────────────────────────────────

    def test_connection(self, cred_id: int) -> dict:
        cred = self._get_or_404(cred_id)
        if not cred.access_token:
            return {"ok": False, "error": "No access token stored"}
        try:
            access_token = decrypt(cred.access_token)
            if cred.platform == "youtube":
                resp = httpx.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                ok = resp.status_code == 200
                return {"ok": ok, "status_code": resp.status_code}
            else:
                return {"ok": True, "note": f"Test not implemented for {cred.platform}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disconnect(self, cred_id: int) -> dict:
        cred = self._get_or_404(cred_id)
        cred.access_token = None
        cred.refresh_token = None
        cred.token_expires_at = None
        cred.status = "disconnected"
        cred.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._safe_dict(cred)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_404(self, cred_id: int) -> PlatformCredential:
        cred = self.db.query(PlatformCredential).filter(PlatformCredential.id == cred_id).first()
        if not cred:
            raise KeyError(f"Credential {cred_id} not found")
        return cred

    def _safe_dict(self, c: PlatformCredential) -> dict:
        """Return credential dict with secrets masked."""
        ttl = None
        if c.token_expires_at:
            remaining = (c.token_expires_at - datetime.now(timezone.utc)).total_seconds()
            ttl = max(0, int(remaining))
        return {
            "id":               c.id,
            "platform":         c.platform,
            "name":             c.name,
            "auth_type":        c.auth_type,
            "status":           c.status,
            "client_id":        c.client_id,
            "client_secret":    "••••••••" if c.client_secret else None,
            "redirect_uri":     c.redirect_uri,
            "scopes":           c.scopes or [],
            "auth_endpoint":    c.auth_endpoint,
            "token_endpoint":   c.token_endpoint,
            "has_access_token": bool(c.access_token),
            "has_refresh_token":bool(c.refresh_token),
            "token_expires_at": c.token_expires_at.isoformat() if c.token_expires_at else None,
            "token_ttl_s":      ttl,
            "last_refreshed":   c.last_refreshed.isoformat() if c.last_refreshed else None,
            "quota_label":      c.quota_label,
            "quota_total":      c.quota_total,
            "quota_used":       c.quota_used,
            "quota_reset_at":   c.quota_reset_at,
            "created_at":       c.created_at.isoformat() if c.created_at else None,
            "updated_at":       c.updated_at.isoformat() if c.updated_at else None,
        }
