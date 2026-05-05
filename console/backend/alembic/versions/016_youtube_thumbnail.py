"""Add thumbnail fields to youtube_videos

Revision ID: 016
Revises: 015
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "thumbnail_asset_id",
            sa.Integer(),
            sa.ForeignKey("video_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("youtube_videos", sa.Column("thumbnail_text", sa.Text(), nullable=True))
    op.add_column("youtube_videos", sa.Column("thumbnail_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("youtube_videos", "thumbnail_path")
    op.drop_column("youtube_videos", "thumbnail_text")
    op.drop_column("youtube_videos", "thumbnail_asset_id")
