from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from console.backend.database import Base
from console.backend.models.credentials import PlatformCredential


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)   # youtube | tiktok | instagram
    credential_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("platform_credentials.id"), nullable=True)
    account_email: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    default_language: Mapped[str] = mapped_column(String, default="vi")
    monetized: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")   # active | paused
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    credential = relationship(PlatformCredential, foreign_keys=[credential_id])


class TemplateChannelDefault(Base):
    __tablename__ = "template_channel_defaults"

    template: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channels.id"), primary_key=True)


class UploadTarget(Base):
    __tablename__ = "upload_targets"

    video_id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channels.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | uploading | published | failed
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    platform_id: Mapped[str | None] = mapped_column(String, nullable=True)  # YouTube/TikTok post ID

    channel = relationship("Channel", foreign_keys=[channel_id])
