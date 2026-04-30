from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class SfxAsset(Base):
    __tablename__ = "sfx_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="import", server_default="import")
    sound_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
