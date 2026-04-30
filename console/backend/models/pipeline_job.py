from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)  # 'scrape'|'generate'|'tts'|'render'|'upload'|'batch'
    status: Mapped[str] = mapped_column(String, default="queued", server_default="queued")  # 'queued'|'running'|'completed'|'failed'|'cancelled'
    script_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    video_format: Mapped[str] = mapped_column(String(20), default="short", server_default="short")
    parent_youtube_video_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
