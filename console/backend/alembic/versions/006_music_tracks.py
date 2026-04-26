"""Add music_tracks table and music_track_id to generated_scripts

Revision ID: 006
Revises: 005
Create Date: 2026-04-26
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "music_tracks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("file_path", sa.String(500)),
        sa.Column("duration_s", sa.Float),
        sa.Column("niches", ARRAY(sa.String), server_default="{}"),
        sa.Column("moods", ARRAY(sa.String), server_default="{}"),
        sa.Column("genres", ARRAY(sa.String), server_default="{}"),
        sa.Column("is_vocal", sa.Boolean, server_default="false"),
        sa.Column("is_favorite", sa.Boolean, server_default="false"),
        sa.Column("volume", sa.Float, server_default="0.15"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("quality_score", sa.Integer, server_default="80"),
        sa.Column("provider", sa.String(20)),
        sa.Column("provider_task_id", sa.String(200)),
        sa.Column("generation_status", sa.String(20), server_default="pending"),
        sa.Column("generation_prompt", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_music_tracks_status", "music_tracks", ["generation_status"])
    op.create_index("idx_music_tracks_provider", "music_tracks", ["provider"])

    op.add_column(
        "generated_scripts",
        sa.Column("music_track_id", sa.Integer, sa.ForeignKey("music_tracks.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_scripts", "music_track_id")
    op.drop_index("idx_music_tracks_provider", table_name="music_tracks")
    op.drop_index("idx_music_tracks_status", table_name="music_tracks")
    op.drop_table("music_tracks")
