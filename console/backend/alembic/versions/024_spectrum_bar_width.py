"""spectrum_bar_width

Revision ID: 024_spectrum_bar_width
Revises: 023_spectrum_style
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa


revision = "024_spectrum_bar_width"
down_revision = "023_spectrum_style"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "spectrum_bar_width_px",
            sa.Float,
            nullable=False,
            server_default="10.0",
        ),
    )
    op.create_check_constraint(
        "spectrum_bar_width_px_range",
        "youtube_videos",
        "spectrum_bar_width_px >= 2.0 AND spectrum_bar_width_px <= 50.0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "spectrum_bar_width_px_range", "youtube_videos", type_="check"
    )
    op.drop_column("youtube_videos", "spectrum_bar_width_px")
