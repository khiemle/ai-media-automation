"""News articles table + language column on generated_scripts

Revision ID: 004
Revises: 003
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── news_articles ─────────────────────────────────────────────────────────
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("main_content", sa.Text),
        sa.Column("language", sa.String, nullable=False, server_default="vietnamese"),
        sa.Column("author", sa.String),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("niche", sa.String),
        sa.Column("tags", postgresql.ARRAY(sa.String)),
        sa.Column("thumbnail_url", sa.String),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("article_id", name="uq_news_articles_article_id"),
        sa.UniqueConstraint("url", name="uq_news_articles_url"),
    )
    op.create_index("idx_news_articles_source",   "news_articles", ["source"])
    op.create_index("idx_news_articles_language", "news_articles", ["language"])
    op.create_index("idx_news_articles_niche",    "news_articles", ["niche"])

    # ── language column on generated_scripts ─────────────────────────────────
    op.add_column(
        "generated_scripts",
        sa.Column("language", sa.String, server_default="vietnamese"),
    )
    op.create_index("idx_gs_language", "generated_scripts", ["language"])


def downgrade() -> None:
    op.drop_index("idx_gs_language", table_name="generated_scripts")
    op.drop_column("generated_scripts", "language")

    op.drop_index("idx_news_articles_niche",    table_name="news_articles")
    op.drop_index("idx_news_articles_language", table_name="news_articles")
    op.drop_index("idx_news_articles_source",   table_name="news_articles")
    op.drop_table("news_articles")
