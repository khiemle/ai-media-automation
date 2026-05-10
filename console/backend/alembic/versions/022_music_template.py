"""music_template

Revision ID: 022_music_template
Revises: d885cdd6570e
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "022_music_template"
down_revision = "d885cdd6570e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ui_features on video_templates
    op.add_column(
        "video_templates",
        sa.Column(
            "ui_features",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE video_templates
           SET ui_features = '["sfx_panel", "duration_picker", "blackout"]'::jsonb
         WHERE slug IN ('asmr', 'soundscape')
        """
    )

    # 2. Insert music template row
    op.execute(
        """
        INSERT INTO video_templates
            (slug, label, output_format, target_duration_h,
             suno_extends_recommended, sfx_pack,
             suno_prompt_template, midjourney_prompt_template,
             runway_prompt_template, sound_rules,
             seo_title_formula, seo_description_template,
             ui_features)
        VALUES (
            'music', 'Music Video', 'landscape_long', NULL, NULL, NULL,
            NULL, NULL, NULL, '[]'::jsonb,
            '{theme} Music — {duration} of Continuous Listening',
            'Curated {theme} music playlist. {duration} of uninterrupted listening.',
            '[]'::jsonb
        )
        ON CONFLICT (slug) DO NOTHING
        """
    )

    # 3. New columns on youtube_videos
    op.add_column("youtube_videos",
        sa.Column("track_transition", sa.String(20),
                  nullable=False, server_default="gapless"))
    op.add_column("youtube_videos",
        sa.Column("track_transition_seconds", sa.Float,
                  nullable=False, server_default="2.0"))
    op.add_column("youtube_videos",
        sa.Column("playlist_overlay_style", sa.String(20), nullable=True))
    op.add_column("youtube_videos",
        sa.Column("spectrum_enabled", sa.Boolean,
                  nullable=False, server_default=sa.text("false")))
    op.add_column("youtube_videos",
        sa.Column("spectrum_position", sa.String(10),
                  nullable=False, server_default="bottom"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_height_pct", sa.Float,
                  nullable=False, server_default="0.12"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_color", sa.String(9),
                  nullable=False, server_default="#ffffff"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_opacity", sa.Float,
                  nullable=False, server_default="0.6"))

    # 4. CHECK constraints
    op.create_check_constraint(
        "track_transition_valid", "youtube_videos",
        "track_transition IN ('gapless', 'crossfade', 'gap')")
    op.create_check_constraint(
        "playlist_overlay_style_valid", "youtube_videos",
        "playlist_overlay_style IS NULL OR "
        "playlist_overlay_style IN ('chip', 'sidebar', 'bottom_bar')")
    op.create_check_constraint(
        "spectrum_position_valid", "youtube_videos",
        "spectrum_position IN ('bottom', 'center')")
    op.create_check_constraint(
        "spectrum_height_pct_range", "youtube_videos",
        "spectrum_height_pct > 0.0 AND spectrum_height_pct <= 0.5")
    op.create_check_constraint(
        "spectrum_opacity_range", "youtube_videos",
        "spectrum_opacity >= 0.0 AND spectrum_opacity <= 1.0")
    op.create_check_constraint(
        "track_transition_seconds_range", "youtube_videos",
        "track_transition_seconds >= 0.5 AND track_transition_seconds <= 10.0")


def downgrade() -> None:
    for name in (
        "track_transition_seconds_range",
        "spectrum_opacity_range",
        "spectrum_height_pct_range",
        "spectrum_position_valid",
        "playlist_overlay_style_valid",
        "track_transition_valid",
    ):
        op.drop_constraint(name, "youtube_videos", type_="check")

    for col in (
        "spectrum_opacity", "spectrum_color", "spectrum_height_pct",
        "spectrum_position", "spectrum_enabled",
        "playlist_overlay_style", "track_transition_seconds",
        "track_transition",
    ):
        op.drop_column("youtube_videos", col)

    op.execute("DELETE FROM youtube_videos WHERE template_id = "
               "(SELECT id FROM video_templates WHERE slug = 'music')")
    op.execute("DELETE FROM video_templates WHERE slug = 'music'")
    op.drop_column("video_templates", "ui_features")
