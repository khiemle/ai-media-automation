from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ARRAY, func
from sqlalchemy.orm import Mapped, mapped_column
from console.backend.database import Base


class PlatformCredential(Base):
    __tablename__ = "platform_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)   # youtube | tiktok | instagram
    name: Mapped[str] = mapped_column(String, nullable=False)
    auth_type: Mapped[str] = mapped_column(String, default="oauth2")
    status: Mapped[str] = mapped_column(String, default="disconnected")  # connected | expired | disconnected

    # OAuth app config
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_secret: Mapped[str | None] = mapped_column(String, nullable=True)   # encrypted (Fernet)
    redirect_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    auth_endpoint: Mapped[str | None] = mapped_column(String, nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String, nullable=True)

    # Active tokens (all encrypted)
    access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Quotas
    quota_label: Mapped[str | None] = mapped_column(String, nullable=True)
    quota_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    quota_reset_at: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
