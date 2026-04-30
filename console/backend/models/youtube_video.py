from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class YoutubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sfx_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_duration_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_quality: Mapped[str] = mapped_column(String(10), default="1080p", server_default="1080p")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
