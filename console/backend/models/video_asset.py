from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # 'pexels'|'veo'|'manual'|'stock'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    niche: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    asset_type: Mapped[str] = mapped_column(String(20), default="video_clip", server_default="video_clip")
    parent_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    runway_status: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
