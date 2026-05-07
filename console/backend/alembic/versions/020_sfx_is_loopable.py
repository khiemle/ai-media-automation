"""add is_loopable to sfx_assets

Revision ID: 020
Revises: 019
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sfx_assets",
        sa.Column("is_loopable", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("sfx_assets", "is_loopable")
