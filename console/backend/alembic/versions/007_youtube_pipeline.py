# console/backend/alembic/versions/007_youtube_pipeline.py
"""YouTube video pipeline — sfx_assets, video_templates, youtube_videos, extensions

Revision ID: 007
Revises: 006
Create Date: 2026-04-30
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sfx_assets ────────────────────────────────────────────────────────────
    op.create_table(
        "sfx_assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("source", sa.String(20), server_default="import"),  # freesound | import
        sa.Column("sound_type", sa.String(50)),
        sa.Column("duration_s", sa.Float),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_sfx_sound_type", "sfx_assets", ["sound_type"])

    # ── video_templates ───────────────────────────────────────────────────────
    op.create_table(
        "video_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("output_format", sa.String(20), nullable=False),  # landscape_long | portrait_short
        sa.Column("target_duration_h", sa.Float),
        sa.Column("suno_extends_recommended", sa.Integer),
        sa.Column("sfx_pack", JSONB),
        sa.Column("suno_prompt_template", sa.Text),
        sa.Column("midjourney_prompt_template", sa.Text),
        sa.Column("runway_prompt_template", sa.Text),
        sa.Column("sound_rules", JSONB),
        sa.Column("seo_title_formula", sa.Text),
        sa.Column("seo_description_template", sa.Text),
    )

    # ── Seed 4 template rows ──────────────────────────────────────────────────
    op.execute("""
        INSERT INTO video_templates
            (slug, label, output_format, target_duration_h, suno_extends_recommended,
             sfx_pack, suno_prompt_template, midjourney_prompt_template, runway_prompt_template,
             sound_rules, seo_title_formula, seo_description_template)
        VALUES
        (
            'asmr', 'ASMR', 'landscape_long', 8.0, 3,
            '{"foreground": {"asset_id": null, "volume": 0.60}, "midground": {"asset_id": null, "volume": 0.30}, "background": {"asset_id": null, "volume": 0.10}}',
            '[Instrumental] heavy rainfall on glass window, distant rolling thunder, no melody, pure texture, [No Vocals], deep and immersive, slight reverb, dark and peaceful, analog warmth, 432Hz, [Sustained Texture]',
            'dark bedroom window at night, heavy rain streaks on glass, blurred city lights beyond, deep navy and charcoal tones, moody atmospheric photography, cinematic depth of field, no people --ar 16:9 --style raw --v 6.1',
            'Very slow, barely perceptible rain droplets running down glass. No camera movement. No sudden changes. Hypnotic loop.',
            '["No melody — melody disrupts sleep", "No sudden volume peaks", "Keep texture consistent throughout", "High-frequency roll-off above 12kHz"]',
            '{theme} ASMR — {duration}h Relaxing Sounds for Sleep & Focus',
            'Immersive {theme} soundscape for deep sleep, focus, and relaxation. {duration} hours of uninterrupted ASMR audio.'
        ),
        (
            'soundscape', 'Soundscape', 'landscape_long', 3.0, 5,
            '{"foreground": {"asset_id": null, "volume": 0.60}, "midground": {"asset_id": null, "volume": 0.30}, "background": {"asset_id": null, "volume": 0.10}}',
            '[Instrumental] babbling mountain stream over smooth rocks, light breeze through pine trees, occasional bird call, subtle ambient music underneath, [No Vocals], peaceful and focused, natural stereo space, fresh morning feel, [Ambient Landscape]',
            'misty mountain valley at dawn, soft light rays through pine forest, still reflective lake in foreground, cool blue-green tones, peaceful nature photography, no people --ar 16:9 --style raw --v 6.1',
            'Gentle mist drifting slowly over a mountain lake. Barely moving pine branches. Golden hour light shifting imperceptibly. Seamless loop.',
            '["Subtle melody ok — keep it understated", "Wide stereo field for spatial depth", "Moderate dynamic range — some variation is welcome", "Natural reverb to place listener in space"]',
            '{theme} Soundscape — {duration}h Ambient Nature Sounds',
            'Peaceful {theme} soundscape for studying, working, and unwinding. {duration} hours of natural ambient audio.'
        ),
        (
            'asmr_viral', 'ASMR Viral Short', 'portrait_short', null, null,
            null,
            '[Instrumental] heavy rainfall on glass window, distant rolling thunder, no melody, pure texture, [No Vocals], deep and immersive, slight reverb, dark and peaceful, analog warmth, 432Hz, [Sustained Texture]',
            null,
            null,
            '["No melody — melody disrupts sleep", "No sudden volume peaks", "Keep texture consistent throughout"]',
            'ASMR {theme} 🌧️ Full {parent_duration}h on channel',
            'Clip from the full {parent_duration}h ASMR video — link in bio.'
        ),
        (
            'soundscape_viral', 'Soundscape Viral Short', 'portrait_short', null, null,
            null,
            '[Instrumental] babbling mountain stream over smooth rocks, light breeze through pine trees, occasional bird call, subtle ambient music underneath, [No Vocals], peaceful and focused, natural stereo space, [Ambient Landscape]',
            null,
            null,
            '["Subtle melody ok", "Wide stereo field", "Moderate dynamic range"]',
            'Soundscape {theme} 🏔️ Full {parent_duration}h on channel',
            'Clip from the full {parent_duration}h soundscape — link in bio.'
        );
    """)

    # ── youtube_videos ────────────────────────────────────────────────────────
    op.create_table(
        "youtube_videos",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("video_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("theme", sa.Text),
        sa.Column("music_track_id", sa.Integer, sa.ForeignKey("music_tracks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visual_asset_id", sa.Integer, sa.ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sfx_overrides", JSONB),
        sa.Column("seo_title", sa.Text),
        sa.Column("seo_description", sa.Text),
        sa.Column("seo_tags", ARRAY(sa.String)),
        sa.Column("target_duration_h", sa.Float),
        sa.Column("output_quality", sa.String(10), server_default="1080p"),
        sa.Column("status", sa.String(20), server_default="draft"),  # draft|rendering|ready|uploaded
        sa.Column("output_path", sa.Text),
        sa.Column("celery_task_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_youtube_videos_status", "youtube_videos", ["status"])
    op.create_index("idx_youtube_videos_template", "youtube_videos", ["template_id"])

    # ── video_assets extensions ───────────────────────────────────────────────
    op.add_column("video_assets", sa.Column("asset_type", sa.String(20), server_default="video_clip"))  # still_image | video_clip
    op.add_column("video_assets", sa.Column("parent_asset_id", sa.Integer, sa.ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True))
    op.add_column("video_assets", sa.Column("generation_prompt", sa.Text, nullable=True))
    op.add_column("video_assets", sa.Column("runway_status", sa.String(20), server_default="none"))  # none|pending|ready|failed

    # ── pipeline_jobs extensions ──────────────────────────────────────────────
    op.add_column("pipeline_jobs", sa.Column("video_format", sa.String(20), server_default="short"))  # short | youtube_long
    op.add_column("pipeline_jobs", sa.Column("parent_youtube_video_id", sa.Integer, sa.ForeignKey("youtube_videos.id", ondelete="SET NULL"), nullable=True))
    op.create_index("idx_pipeline_jobs_format", "pipeline_jobs", ["video_format"])

    # ── music_tracks: rename suno → sunoapi ──────────────────────────────────
    op.execute("UPDATE music_tracks SET provider = 'sunoapi' WHERE provider = 'suno'")


def downgrade() -> None:
    op.execute("UPDATE music_tracks SET provider = 'suno' WHERE provider = 'sunoapi'")
    op.drop_index("idx_pipeline_jobs_format", table_name="pipeline_jobs")
    op.drop_column("pipeline_jobs", "parent_youtube_video_id")
    op.drop_column("pipeline_jobs", "video_format")
    op.drop_column("video_assets", "runway_status")
    op.drop_column("video_assets", "generation_prompt")
    op.drop_column("video_assets", "parent_asset_id")
    op.drop_column("video_assets", "asset_type")
    op.drop_index("idx_youtube_videos_template", table_name="youtube_videos")
    op.drop_index("idx_youtube_videos_status", table_name="youtube_videos")
    op.drop_table("youtube_videos")
    op.drop_table("video_templates")
    op.drop_index("idx_sfx_sound_type", table_name="sfx_assets")
    op.drop_table("sfx_assets")
