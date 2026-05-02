"""channel_plans — channel strategy document storage

Revision ID: 012
Revises: 011
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("focus", sa.Text, nullable=True),
        sa.Column("upload_frequency", sa.Text, nullable=True),
        sa.Column("rpm_estimate", sa.Text, nullable=True),
        sa.Column("md_content", sa.Text, nullable=False),
        sa.Column("md_filename", sa.Text, nullable=True),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_channel_plans_slug", "channel_plans", ["slug"])
    op.create_index("ix_channel_plans_slug", "channel_plans", ["slug"])


def downgrade() -> None:
    op.drop_table("channel_plans")
