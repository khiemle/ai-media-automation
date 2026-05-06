"""add topaz upscale columns to video_assets

Revision ID: 019
Revises: 018
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("video_assets", sa.Column("upscale_task_id", sa.String(100), nullable=True))
    op.add_column("video_assets", sa.Column("topaz_request_id", sa.String(100), nullable=True))
    op.add_column("video_assets", sa.Column("upscale_status", sa.String(20), nullable=True))
    op.add_column("video_assets", sa.Column("original_asset_id", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("video_assets", "original_asset_id")
    op.drop_column("video_assets", "upscale_status")
    op.drop_column("video_assets", "topaz_request_id")
    op.drop_column("video_assets", "upscale_task_id")
