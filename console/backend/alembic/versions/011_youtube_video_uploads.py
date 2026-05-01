"""youtube_video_uploads — track per-channel upload history

Revision ID: 011
Revises: 010
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "youtube_video_uploads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "youtube_video_id",
            sa.Integer,
            sa.ForeignKey("youtube_videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("platform_id", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("celery_task_id", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_youtube_video_channel",
        "youtube_video_uploads",
        ["youtube_video_id", "channel_id"],
    )
    op.create_index("ix_youtube_video_uploads_video_id", "youtube_video_uploads", ["youtube_video_id"])


def downgrade() -> None:
    op.drop_table("youtube_video_uploads")
