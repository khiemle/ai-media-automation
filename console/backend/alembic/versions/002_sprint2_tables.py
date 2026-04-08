"""Sprint 2 tables: video_assets and pipeline_jobs

Revision ID: 002
Revises: 001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. video_assets ───────────────────────────────────────────────────────
    op.create_table(
        "video_assets",
        sa.Column("id",             sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("file_path",      sa.Text(),       nullable=False),
        sa.Column("thumbnail_path", sa.Text(),       nullable=True),
        sa.Column("source",         sa.String(),     nullable=True),
        sa.Column("keywords",       postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("niche",          postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("duration_s",     sa.Float(),      nullable=True),
        sa.Column("resolution",     sa.String(),     nullable=True),
        sa.Column("quality_score",  sa.Float(),      server_default="0.0"),
        sa.Column("usage_count",    sa.Integer(),    server_default="0"),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 2. pipeline_jobs ──────────────────────────────────────────────────────
    # Check if generated_scripts table exists before adding FK
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    has_generated_scripts = "generated_scripts" in inspector.get_table_names()

    if has_generated_scripts:
        op.create_table(
            "pipeline_jobs",
            sa.Column("id",             sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_type",       sa.String(),  nullable=False),
            sa.Column("status",         sa.String(),  server_default="queued"),
            sa.Column("script_id",      sa.Integer(),
                      sa.ForeignKey("generated_scripts.id", ondelete="SET NULL"),
                      nullable=True),
            sa.Column("celery_task_id", sa.Text(),    nullable=True),
            sa.Column("progress",       sa.Integer(), server_default="0"),
            sa.Column("details",        postgresql.JSONB(), nullable=True),
            sa.Column("error",          sa.Text(),    nullable=True),
            sa.Column("started_at",     sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at",   sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    else:
        op.create_table(
            "pipeline_jobs",
            sa.Column("id",             sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_type",       sa.String(),  nullable=False),
            sa.Column("status",         sa.String(),  server_default="queued"),
            sa.Column("script_id",      sa.Integer(), nullable=True),
            sa.Column("celery_task_id", sa.Text(),    nullable=True),
            sa.Column("progress",       sa.Integer(), server_default="0"),
            sa.Column("details",        postgresql.JSONB(), nullable=True),
            sa.Column("error",          sa.Text(),    nullable=True),
            sa.Column("started_at",     sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at",   sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # Add check constraints
    op.create_check_constraint(
        "ck_pipeline_jobs_status",
        "pipeline_jobs",
        "status IN ('queued','running','completed','failed','cancelled')",
    )
    op.create_check_constraint(
        "ck_pipeline_jobs_job_type",
        "pipeline_jobs",
        "job_type IN ('scrape','generate','tts','render','upload','batch')",
    )


def downgrade() -> None:
    op.drop_table("pipeline_jobs")
    op.drop_table("video_assets")
