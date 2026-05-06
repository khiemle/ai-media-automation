"""add runway_invocation_id to video_assets

Revision ID: 018
Revises: 017
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "video_assets",
        sa.Column("runway_invocation_id", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("video_assets", "runway_invocation_id")
