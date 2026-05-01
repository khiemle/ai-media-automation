# console/backend/alembic/versions/009_youtube_video_parent.py
"""youtube_videos — add parent_youtube_video_id self-FK

Revision ID: 009
Revises: 008
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "parent_youtube_video_id",
            sa.Integer,
            sa.ForeignKey("youtube_videos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_videos", "parent_youtube_video_id")
