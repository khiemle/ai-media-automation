from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class ChannelPlan(Base):
    __tablename__ = "channel_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpm_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
    md_content: Mapped[str] = mapped_column(Text, nullable=False)
    md_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
