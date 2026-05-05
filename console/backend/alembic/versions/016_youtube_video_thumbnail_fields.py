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
    # Use IF NOT EXISTS so this is safe to run against a DB that already has
    # these columns (e.g. columns were added directly before this migration).
    op.execute("""
        ALTER TABLE youtube_videos
            ADD COLUMN IF NOT EXISTS thumbnail_asset_id INTEGER
                REFERENCES video_assets(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS thumbnail_text TEXT,
            ADD COLUMN IF NOT EXISTS thumbnail_path TEXT
    """)


def downgrade() -> None:
    op.drop_column("youtube_videos", "thumbnail_path")
    op.drop_column("youtube_videos", "thumbnail_text")
    op.drop_column("youtube_videos", "thumbnail_asset_id")
