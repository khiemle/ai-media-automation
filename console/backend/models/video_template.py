from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class VideoTemplate(Base):
    __tablename__ = "video_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), nullable=False)
    target_duration_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    suno_extends_recommended: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sfx_pack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suno_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    midjourney_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    runway_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    sound_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    seo_title_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description_template: Mapped[str | None] = mapped_column(Text, nullable=True)
