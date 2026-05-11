"""spectrum_style

Revision ID: 023_spectrum_style
Revises: 022_music_template
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa


revision = "023_spectrum_style"
down_revision = "022_music_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "spectrum_style",
            sa.String(20),
            nullable=False,
            server_default="classic",
        ),
    )
    op.create_check_constraint(
        "spectrum_style_valid",
        "youtube_videos",
        "spectrum_style IN ('classic', 'bars')",
    )


def downgrade() -> None:
    op.drop_constraint("spectrum_style_valid", "youtube_videos", type_="check")
    op.drop_column("youtube_videos", "spectrum_style")
