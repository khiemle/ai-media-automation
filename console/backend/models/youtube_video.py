from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, DateTime, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class YoutubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("video_templates.id", ondelete="RESTRICT"), nullable=False
    )
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_youtube_video_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("youtube_videos.id", ondelete="SET NULL"),
        nullable=True,
    )
    sfx_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_duration_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_quality: Mapped[str] = mapped_column(String(10), default="1080p", server_default="1080p")
    status: Mapped[str] = mapped_column(String(40), default="draft", server_default="draft")
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

    # ASMR/soundscape extension (added by migration 013)
    music_track_ids:     Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    sfx_pool:            Mapped[list[dict] | None] = mapped_column(JSONB, default=list, server_default="[]")
    sfx_density_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sfx_seed:            Mapped[int | None] = mapped_column(Integer, nullable=True)
    black_from_seconds:  Mapped[int | None] = mapped_column(Integer, nullable=True)
    skip_previews:       Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    render_parts:        Mapped[list[dict] | None] = mapped_column(JSONB, default=list, server_default="[]")
    sound_layers:        Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    audio_preview_path:  Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_preview_path:  Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Visual playlist + loop mode (added by migration 015)
    visual_asset_ids:        Mapped[list[int]]   = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    visual_clip_durations_s: Mapped[list[float]] = mapped_column(ARRAY(Float),   default=list, server_default="{}")
    visual_loop_mode:        Mapped[str]         = mapped_column(String(20), default="concat_loop", server_default="concat_loop", nullable=False)

    # Thumbnail fields (added by migration 016)
    thumbnail_asset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True
    )
    thumbnail_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Music template fields (added by migration 022)
    track_transition:         Mapped[str]       = mapped_column(String(20),  nullable=False, default="gapless",  server_default="gapless")
    track_transition_seconds: Mapped[float]     = mapped_column(Float,       nullable=False, default=2.0,        server_default="2.0")
    playlist_overlay_style:   Mapped[str | None] = mapped_column(String(20), nullable=True)
    spectrum_enabled:         Mapped[bool]      = mapped_column(Boolean,     nullable=False, default=False,      server_default=text("false"))
    spectrum_position:        Mapped[str]       = mapped_column(String(10),  nullable=False, default="bottom",   server_default="bottom")
    spectrum_height_pct:      Mapped[float]     = mapped_column(Float,       nullable=False, default=0.12,       server_default="0.12")
    spectrum_color:           Mapped[str]       = mapped_column(String(9),   nullable=False, default="#ffffff",  server_default="#ffffff")
    spectrum_opacity:         Mapped[float]     = mapped_column(Float,       nullable=False, default=0.6,        server_default="0.6")
    spectrum_style:           Mapped[str]       = mapped_column(String(20),  nullable=False, default="classic",  server_default="classic")
    spectrum_bar_width_px:    Mapped[float]     = mapped_column(Float,       nullable=False, default=10.0,       server_default="10.0")
