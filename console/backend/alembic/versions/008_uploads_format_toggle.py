# console/backend/alembic/versions/008_uploads_format_toggle.py
"""Uploads page — add video_format and duration_s to generated_scripts

Revision ID: 008
Revises: 007
Create Date: 2026-04-30
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add video_format to generated_scripts
    op.add_column("generated_scripts", sa.Column("video_format", sa.String(20), server_default="short"))
    # Add duration_s to generated_scripts
    op.add_column("generated_scripts", sa.Column("duration_s", sa.Float, nullable=True))
    op.create_index("idx_generated_scripts_format", "generated_scripts", ["video_format"])


def downgrade() -> None:
    op.drop_index("idx_generated_scripts_format", table_name="generated_scripts")
    op.drop_column("generated_scripts", "duration_s")
    op.drop_column("generated_scripts", "video_format")
