"""Widen youtube_videos.status from VARCHAR(20) to VARCHAR(40)

The new ASMR/soundscape preview states (audio_preview_rendering,
video_preview_rendering — both 23 chars) overflow the original 20-char limit.

Revision ID: 014
Revises: 013
Create Date: 2026-05-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "youtube_videos", "status",
        existing_type=sa.String(20),
        type_=sa.String(40),
        existing_server_default="draft",
        existing_nullable=False,
    )


def downgrade() -> None:
    # NOTE: this will fail if any row has a status > 20 chars at downgrade time.
    op.alter_column(
        "youtube_videos", "status",
        existing_type=sa.String(40),
        type_=sa.String(20),
        existing_server_default="draft",
        existing_nullable=False,
    )
