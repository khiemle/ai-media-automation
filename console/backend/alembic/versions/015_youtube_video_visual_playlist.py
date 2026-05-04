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


def downgrade() -> None:
    op.drop_column("youtube_videos", "visual_loop_mode")
    op.drop_column("youtube_videos", "visual_clip_durations_s")
    op.drop_column("youtube_videos", "visual_asset_ids")
