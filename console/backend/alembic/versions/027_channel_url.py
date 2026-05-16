"""channel_url column on channels

Revision ID: 027_channel_url
Revises: 026_thumbnail_bold_word_count
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

revision = "027_channel_url"
down_revision = "026_thumbnail_bold_word_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("channel_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "channel_url")
