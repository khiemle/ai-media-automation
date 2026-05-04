"""Add visual playlist + loop mode fields to youtube_videos

Revision ID: 015
Revises: 014
Create Date: 2026-05-04
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column("visual_asset_ids", ARRAY(sa.Integer), server_default="{}", nullable=False),
    )
    op.add_column(
        "youtube_videos",
        sa.Column("visual_clip_durations_s", ARRAY(sa.Float), server_default="{}", nullable=False),
    )
    op.add_column(
        "youtube_videos",
        sa.Column(
            "visual_loop_mode",
            sa.String(20),
            server_default="concat_loop",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_youtube_videos_visual_loop_mode",
        "youtube_videos",
        "visual_loop_mode IN ('concat_loop', 'per_clip')",
    )


def downgrade() -> None:
    # Use IF EXISTS so a re-run downgrade is idempotent and safe even if the
    # constraint was never created (e.g. when rolling back a migration that was
    # first applied without the constraint).
    op.execute(
        "ALTER TABLE youtube_videos DROP CONSTRAINT IF EXISTS ck_youtube_videos_visual_loop_mode"
    )
    op.drop_column("youtube_videos", "visual_loop_mode")
    op.drop_column("youtube_videos", "visual_clip_durations_s")
    op.drop_column("youtube_videos", "visual_asset_ids")
