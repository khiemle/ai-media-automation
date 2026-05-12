"""thumbnail_bold_word_count column

Revision ID: 026_thumbnail_bold_word_count
Revises: 025_spectrum_bar_count_and_align
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "026_thumbnail_bold_word_count"
down_revision = "025_spectrum_bar_count_and_align"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "thumbnail_bold_word_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_videos", "thumbnail_bold_word_count")
