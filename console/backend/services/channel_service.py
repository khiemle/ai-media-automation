"""ChannelService — CRUD for channels and template→channel defaults."""
import math
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from console.backend.models.channel import Channel, TemplateChannelDefault, UploadTarget
from console.backend.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class ChannelService:
    def __init__(self, db: Session):
        self.db = db

    # ── Channels ──────────────────────────────────────────────────────────────

    def list_channels(self, platform: str | None = None, status: str | None = None) -> list[dict]:
        q = self.db.query(Channel)
        if platform:
            q = q.filter(Channel.platform == platform)
        if status:
            q = q.filter(Channel.status == status)
        return [self._ch_dict(c) for c in q.order_by(Channel.platform, Channel.name).all()]

    def get_channel(self, channel_id: int) -> dict:
        ch = self._ch_or_404(channel_id)
        return self._ch_dict(ch)

    def create_channel(self, data: dict) -> dict:
        ch = Channel(
            name=data["name"],
            platform=data["platform"],
            credential_id=data.get("credential_id"),
            account_email=data.get("account_email"),
            category=data.get("category"),
            default_language=data.get("default_language", "vi"),
            monetized=data.get("monetized", False),
            status=data.get("status", "active"),
            subscriber_count=data.get("subscriber_count", 0),
            video_count=data.get("video_count", 0),
        )
        self.db.add(ch)
        self.db.commit()
        self.db.refresh(ch)
        logger.info(f"Created channel {ch.id} ({ch.platform}/{ch.name})")
        return self._ch_dict(ch)

    def update_channel(self, channel_id: int, data: dict) -> dict:
        ch = self._ch_or_404(channel_id)
        for field in ("name", "platform", "credential_id", "account_email",
                      "category", "default_language", "monetized", "status",
                      "subscriber_count", "video_count"):
            if field in data:
                setattr(ch, field, data[field])
        self.db.commit()
        self.db.refresh(ch)
        return self._ch_dict(ch)

    def delete_channel(self, channel_id: int) -> None:
        ch = self._ch_or_404(channel_id)
        self.db.delete(ch)
        self.db.commit()
        logger.info(f"Deleted channel {channel_id}")

    # ── Template defaults ─────────────────────────────────────────────────────

    def get_defaults(self, template: str) -> list[int]:
        rows = self.db.query(TemplateChannelDefault).filter(
            TemplateChannelDefault.template == template
        ).all()
        return [r.channel_id for r in rows]

    def set_defaults(self, template: str, channel_ids: list[int]) -> list[int]:
        # Delete existing
        self.db.query(TemplateChannelDefault).filter(
            TemplateChannelDefault.template == template
        ).delete()
        # Insert new
        for cid in channel_ids:
            self.db.add(TemplateChannelDefault(template=template, channel_id=cid))
        self.db.commit()
        return channel_ids

    def list_all_defaults(self) -> dict[str, list[int]]:
        rows = self.db.query(TemplateChannelDefault).all()
        result: dict[str, list[int]] = {}
        for r in rows:
            result.setdefault(r.template, []).append(r.channel_id)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ch_or_404(self, channel_id: int) -> Channel:
        ch = self.db.query(Channel).filter(Channel.id == channel_id).first()
        if not ch:
            raise KeyError(f"Channel {channel_id} not found")
        return ch

    def _ch_dict(self, c: Channel) -> dict:
        return {
            "id":               c.id,
            "name":             c.name,
            "platform":         c.platform,
            "credential_id":    c.credential_id,
            "account_email":    c.account_email,
            "category":         c.category,
            "default_language": c.default_language,
            "monetized":        c.monetized,
            "status":           c.status,
            "subscriber_count": c.subscriber_count,
            "video_count":      c.video_count,
            "created_at":       c.created_at.isoformat() if c.created_at else None,
        }
