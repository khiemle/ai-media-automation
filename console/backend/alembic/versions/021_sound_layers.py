"""add sound_layers to youtube_videos

Revision ID: 021
Revises: 020
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "youtube_videos",
        sa.Column("sound_layers", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("youtube_videos", "sound_layers")
