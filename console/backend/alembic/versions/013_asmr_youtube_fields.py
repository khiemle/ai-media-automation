"""Add ASMR/soundscape fields to youtube_videos

Revision ID: 013
Revises: 012
Create Date: 2026-05-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("youtube_videos",
        sa.Column("music_track_ids", ARRAY(sa.Integer), server_default="{}"))
    op.add_column("youtube_videos",
        sa.Column("sfx_pool", JSONB, server_default="[]"))
    op.add_column("youtube_videos",
        sa.Column("sfx_density_seconds", sa.Integer, nullable=True))
    op.add_column("youtube_videos",
        sa.Column("sfx_seed", sa.Integer, nullable=True))
    op.add_column("youtube_videos",
        sa.Column("black_from_seconds", sa.Integer, nullable=True))
    op.add_column("youtube_videos",
        sa.Column("skip_previews", sa.Boolean, server_default="true", nullable=False))
    op.add_column("youtube_videos",
        sa.Column("render_parts", JSONB, server_default="[]"))
    op.add_column("youtube_videos",
        sa.Column("audio_preview_path", sa.String(500), nullable=True))
    op.add_column("youtube_videos",
        sa.Column("video_preview_path", sa.String(500), nullable=True))

    # Backfill music_track_ids from existing music_track_id where set
    op.execute("""
        UPDATE youtube_videos
        SET music_track_ids = ARRAY[music_track_id]
        WHERE music_track_id IS NOT NULL
    """)

    # Set skip_previews=false for existing asmr/soundscape rows
    op.execute("""
        UPDATE youtube_videos yv
        SET skip_previews = false
        FROM video_templates vt
        WHERE yv.template_id = vt.id
          AND vt.slug IN ('asmr', 'soundscape')
    """)


def downgrade() -> None:
    op.drop_column("youtube_videos", "video_preview_path")
    op.drop_column("youtube_videos", "audio_preview_path")
    op.drop_column("youtube_videos", "render_parts")
    op.drop_column("youtube_videos", "skip_previews")
    op.drop_column("youtube_videos", "black_from_seconds")
    op.drop_column("youtube_videos", "sfx_seed")
    op.drop_column("youtube_videos", "sfx_density_seconds")
    op.drop_column("youtube_videos", "sfx_pool")
    op.drop_column("youtube_videos", "music_track_ids")
