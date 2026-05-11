"""spectrum_bar_count_and_align

Revision ID: 025_spectrum_bar_count_and_align
Revises: 024_spectrum_bar_width
Create Date: 2026-05-12

Adds:
  - spectrum_bar_count INT default 50, range 5..200
  - spectrum_align_horizontal VARCHAR(10) default 'center', range left/center/right
  - spectrum_align_vertical VARCHAR(10) default 'bottom', range top/center/bottom

Replaces:
  - spectrum_position (bottom|center) → spectrum_align_vertical (top|center|bottom);
    bottom → bottom, center → center; spectrum_align_horizontal defaults to 'center'.

After backfill, the legacy spectrum_position column is dropped.
"""
from alembic import op
import sqlalchemy as sa


revision = "025_spectrum_bar_count_and_align"
down_revision = "024_spectrum_bar_width"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns with defaults
    op.add_column(
        "youtube_videos",
        sa.Column("spectrum_bar_count", sa.Integer,
                  nullable=False, server_default="50"),
    )
    op.add_column(
        "youtube_videos",
        sa.Column("spectrum_align_horizontal", sa.String(10),
                  nullable=False, server_default="center"),
    )
    op.add_column(
        "youtube_videos",
        sa.Column("spectrum_align_vertical", sa.String(10),
                  nullable=False, server_default="bottom"),
    )

    # 2. Backfill spectrum_align_vertical from spectrum_position
    op.execute(
        "UPDATE youtube_videos SET spectrum_align_vertical = spectrum_position"
    )

    # 3. CHECK constraints
    op.create_check_constraint(
        "spectrum_bar_count_range", "youtube_videos",
        "spectrum_bar_count >= 5 AND spectrum_bar_count <= 200",
    )
    op.create_check_constraint(
        "spectrum_align_horizontal_valid", "youtube_videos",
        "spectrum_align_horizontal IN ('left', 'center', 'right')",
    )
    op.create_check_constraint(
        "spectrum_align_vertical_valid", "youtube_videos",
        "spectrum_align_vertical IN ('top', 'center', 'bottom')",
    )

    # 4. Drop legacy spectrum_position
    op.drop_constraint("spectrum_position_valid", "youtube_videos", type_="check")
    op.drop_column("youtube_videos", "spectrum_position")


def downgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column("spectrum_position", sa.String(10),
                  nullable=False, server_default="bottom"),
    )
    op.create_check_constraint(
        "spectrum_position_valid", "youtube_videos",
        "spectrum_position IN ('bottom', 'center')",
    )
    # Backfill spectrum_position from spectrum_align_vertical (top → center)
    op.execute(
        "UPDATE youtube_videos SET spectrum_position = "
        "CASE WHEN spectrum_align_vertical = 'top' THEN 'center' "
        "ELSE spectrum_align_vertical END"
    )
    op.drop_constraint("spectrum_align_vertical_valid", "youtube_videos", type_="check")
    op.drop_constraint("spectrum_align_horizontal_valid", "youtube_videos", type_="check")
    op.drop_constraint("spectrum_bar_count_range", "youtube_videos", type_="check")
    op.drop_column("youtube_videos", "spectrum_align_vertical")
    op.drop_column("youtube_videos", "spectrum_align_horizontal")
    op.drop_column("youtube_videos", "spectrum_bar_count")
