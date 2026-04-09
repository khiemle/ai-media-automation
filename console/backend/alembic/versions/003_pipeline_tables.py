"""Core pipeline tables: viral_videos, generated_scripts, viral_patterns + video_assets extensions

Revision ID: 003
Revises: 002
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── 1. viral_videos ───────────────────────────────────────────────────────
    if "viral_videos" not in existing_tables:
        op.create_table(
            "viral_videos",
            sa.Column("id",            sa.Integer(),    primary_key=True, autoincrement=True),
            sa.Column("video_id",      sa.String(),     nullable=False, unique=True),
            sa.Column("source",        sa.String(),     nullable=False),
            sa.Column("author",        sa.String(),     nullable=True),
            sa.Column("hook_text",     sa.Text(),       nullable=True),
            sa.Column("play_count",    sa.BigInteger(), server_default="0"),
            sa.Column("like_count",    sa.BigInteger(), server_default="0"),
            sa.Column("share_count",   sa.BigInteger(), server_default="0"),
            sa.Column("comment_count", sa.BigInteger(), server_default="0"),
            sa.Column("duration_s",    sa.Float(),      nullable=True),
            sa.Column("niche",         sa.String(),     nullable=True),
            sa.Column("region",        sa.String(),     server_default="vn"),
            sa.Column("tags",          postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("thumbnail_url", sa.String(),     nullable=True),
            sa.Column("video_url",     sa.String(),     nullable=True),
            sa.Column("indexed_at",    sa.DateTime(timezone=True), nullable=True),
            sa.Column("scraped_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_viral_videos_niche",      "viral_videos", ["niche"])
        op.create_index("idx_viral_videos_play_count", "viral_videos", ["play_count"])
        op.create_index("idx_viral_videos_source",     "viral_videos", ["source"])

    # ── 2. generated_scripts ──────────────────────────────────────────────────
    if "generated_scripts" not in existing_tables:
        op.create_table(
            "generated_scripts",
            sa.Column("id",               sa.Integer(),    primary_key=True, autoincrement=True),
            sa.Column("topic",            sa.String(),     nullable=False),
            sa.Column("niche",            sa.String(),     nullable=True),
            sa.Column("template",         sa.String(),     nullable=True),
            sa.Column("region",           sa.String(),     server_default="vn"),
            sa.Column("script_json",      postgresql.JSONB(), nullable=False),
            sa.Column("llm_used",         sa.String(),     nullable=True),
            sa.Column("source_video_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
            sa.Column("output_path",      sa.Text(),       nullable=True),
            # Console extension columns
            sa.Column("status",           sa.String(),     server_default="draft"),
            sa.Column("editor_notes",     sa.Text(),       nullable=True),
            sa.Column("edited_by",        sa.Integer(),
                      sa.ForeignKey("console_users.id"), nullable=True),
            sa.Column("approved_at",      sa.DateTime(timezone=True), nullable=True),
            # Feedback columns
            sa.Column("quality_score",    sa.Float(),      nullable=True),
            sa.Column("platform_video_id", sa.String(),    nullable=True),
            sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.execute(
            "ALTER TABLE generated_scripts ADD CONSTRAINT ck_scripts_status_003 "
            "CHECK (status IN ('draft','pending_review','approved','rejected','editing','producing','completed'))"
        )
        op.create_index("idx_gs_status",    "generated_scripts", ["status"])
        op.create_index("idx_gs_niche",     "generated_scripts", ["niche"])
        op.create_index("idx_gs_template",  "generated_scripts", ["template"])
    else:
        # Table already exists — add any missing columns
        existing_cols = {c["name"] for c in inspector.get_columns("generated_scripts")}

        cols_to_add = [
            ("llm_used",          sa.Column("llm_used",          sa.String(),  nullable=True)),
            ("source_video_ids",  sa.Column("source_video_ids",  postgresql.ARRAY(sa.Integer()), nullable=True)),
            ("output_path",       sa.Column("output_path",        sa.Text(),    nullable=True)),
            ("quality_score",     sa.Column("quality_score",      sa.Float(),   nullable=True)),
            ("platform_video_id", sa.Column("platform_video_id",  sa.String(),  nullable=True)),
            ("updated_at",        sa.Column("updated_at",          sa.DateTime(timezone=True),
                                            server_default=sa.func.now())),
        ]
        for col_name, col_def in cols_to_add:
            if col_name not in existing_cols:
                op.add_column("generated_scripts", col_def)

    # ── 3. viral_patterns ────────────────────────────────────────────────────
    if "viral_patterns" not in existing_tables:
        op.create_table(
            "viral_patterns",
            sa.Column("id",               sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("niche",            sa.String(),  nullable=False),
            sa.Column("region",           sa.String(),  server_default="vn"),
            sa.Column("hook_templates",   postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("scene_types",      postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("cta_phrases",      postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("hashtag_clusters", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("avg_duration_s",   sa.Float(),      nullable=True),
            sa.Column("avg_play_count",   sa.BigInteger(), nullable=True),
            sa.Column("sample_count",     sa.Integer(),    server_default="0"),
            sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # ── 4. Extend video_assets (add missing columns from migration 002) ───────
    if "video_assets" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("video_assets")}
        extra_cols = [
            ("file_hash",    sa.Column("file_hash",    sa.String(), unique=True, nullable=True)),
            ("source_id",    sa.Column("source_id",    sa.String(), nullable=True)),
            ("veo_prompt",   sa.Column("veo_prompt",   sa.Text(),   nullable=True)),
            ("tags",         sa.Column("tags",         postgresql.ARRAY(sa.String()), nullable=True)),
            ("description",  sa.Column("description",  sa.Text(),   nullable=True)),
            ("aspect_ratio", sa.Column("aspect_ratio", sa.String(), server_default="9:16")),
            ("fps",          sa.Column("fps",          sa.Integer(), server_default="30")),
            ("file_size_mb", sa.Column("file_size_mb", sa.Float(),  nullable=True)),
            ("last_used_at", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)),
            ("expires_at",   sa.Column("expires_at",   sa.DateTime(timezone=True), nullable=True)),
        ]
        for col_name, col_def in extra_cols:
            if col_name not in existing_cols:
                op.add_column("video_assets", col_def)

        # Add GIN indexes for array columns if not exists
        try:
            op.create_index("idx_va_keywords", "video_assets", ["keywords"], postgresql_using="gin")
        except Exception:
            pass
        try:
            op.create_index("idx_va_niche_arr", "video_assets", ["niche"], postgresql_using="gin")
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "viral_patterns" in existing_tables:
        op.drop_table("viral_patterns")

    if "generated_scripts" in existing_tables:
        # Only drop if we created it (check for llm_used column which only exists in our version)
        cols = {c["name"] for c in inspector.get_columns("generated_scripts")}
        if "llm_used" in cols:
            op.drop_table("generated_scripts")

    if "viral_videos" in existing_tables:
        op.drop_table("viral_videos")
