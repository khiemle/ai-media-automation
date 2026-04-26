"""Add niches table

Revision ID: 005
Revises: 004
Create Date: 2026-04-26
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_NICHES = ["beauty", "education", "finance", "fitness", "food", "lifestyle", "tech"]


def upgrade() -> None:
    op.create_table(
        "niches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_niches_name", "niches", ["name"])

    # Seed default niches
    op.bulk_insert(
        sa.table("niches", sa.column("name", sa.String)),
        [{"name": n} for n in SEED_NICHES],
    )


def downgrade() -> None:
    op.drop_index("idx_niches_name", table_name="niches")
    op.drop_table("niches")
