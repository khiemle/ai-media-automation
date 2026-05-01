"""video_templates — add short_cta_text and short_duration_s

Revision ID: 010
Revises: 009
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_templates", sa.Column("short_cta_text", sa.Text, nullable=True))
    op.add_column(
        "video_templates",
        sa.Column("short_duration_s", sa.Integer, nullable=True, server_default="58"),
    )


def downgrade() -> None:
    op.drop_column("video_templates", "short_duration_s")
    op.drop_column("video_templates", "short_cta_text")
