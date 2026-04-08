"""Initial console tables

Revision ID: 001
Revises:
Create Date: 2026-04-08

Creates 6 new tables for the Management Console and extends generated_scripts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. console_users ──────────────────────────────────────────────────────
    op.create_table(
        "console_users",
        sa.Column("id",            sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("username",      sa.String(),     nullable=False,   unique=True),
        sa.Column("email",         sa.String(),     nullable=False,   unique=True),
        sa.Column("password_hash", sa.String(),     nullable=False),
        sa.Column("role",          sa.String(),     nullable=False,   server_default="editor"),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login",    sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'editor')", name="ck_console_users_role"),
    )

    # ── 2. platform_credentials ───────────────────────────────────────────────
    op.create_table(
        "platform_credentials",
        sa.Column("id",              sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform",        sa.String(), nullable=False),
        sa.Column("name",            sa.String(), nullable=False),
        sa.Column("auth_type",       sa.String(), server_default="oauth2"),
        sa.Column("status",          sa.String(), server_default="disconnected"),
        sa.Column("client_id",       sa.String(), nullable=True),
        sa.Column("client_secret",   sa.String(), nullable=True),
        sa.Column("redirect_uri",    sa.String(), nullable=True),
        sa.Column("scopes",          postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("auth_endpoint",   sa.String(), nullable=True),
        sa.Column("token_endpoint",  sa.String(), nullable=True),
        sa.Column("access_token",    sa.String(), nullable=True),
        sa.Column("refresh_token",   sa.String(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("quota_label",     sa.String(), nullable=True),
        sa.Column("quota_total",     sa.Integer(), nullable=True),
        sa.Column("quota_used",      sa.Integer(), server_default="0"),
        sa.Column("quota_reset_at",  sa.String(), nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 3. channels ───────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id",               sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name",             sa.String(), nullable=False),
        sa.Column("platform",         sa.String(), nullable=False),
        sa.Column("credential_id",    sa.Integer(), sa.ForeignKey("platform_credentials.id"), nullable=True),
        sa.Column("account_email",    sa.String(), nullable=True),
        sa.Column("category",         sa.String(), nullable=True),
        sa.Column("default_language", sa.String(), server_default="vi"),
        sa.Column("monetized",        sa.Boolean(), server_default="false"),
        sa.Column("status",           sa.String(), server_default="active"),
        sa.Column("subscriber_count", sa.Integer(), server_default="0"),
        sa.Column("video_count",      sa.Integer(), server_default="0"),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 4. template_channel_defaults ──────────────────────────────────────────
    op.create_table(
        "template_channel_defaults",
        sa.Column("template",   sa.String(),  primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id"), primary_key=True),
    )

    # ── 5. upload_targets ─────────────────────────────────────────────────────
    op.create_table(
        "upload_targets",
        sa.Column("video_id",    sa.String(),  primary_key=True),
        sa.Column("channel_id",  sa.Integer(), sa.ForeignKey("channels.id"), primary_key=True),
        sa.Column("status",      sa.String(),  server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_id", sa.String(),  nullable=True),
    )

    # ── 6. audit_log ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id",          sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id",     sa.Integer(), sa.ForeignKey("console_users.id"), nullable=True),
        sa.Column("action",      sa.String(),  nullable=False),
        sa.Column("target_type", sa.String(),  nullable=True),
        sa.Column("target_id",   sa.String(),  nullable=True),
        sa.Column("details",     postgresql.JSONB(), nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 7. Extend generated_scripts ───────────────────────────────────────────
    # Only add columns if the table exists (it belongs to the core pipeline).
    # We check with a try/except to be safe if the table doesn't exist yet.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "generated_scripts" in existing_tables:
        existing_cols = [c["name"] for c in inspector.get_columns("generated_scripts")]

        if "status" not in existing_cols:
            op.add_column("generated_scripts", sa.Column(
                "status", sa.String(), nullable=True, server_default="draft"
            ))
            op.execute(
                "ALTER TABLE generated_scripts ADD CONSTRAINT ck_scripts_status "
                "CHECK (status IN ('draft','pending_review','approved','rejected','editing','producing','completed'))"
            )

        if "editor_notes" not in existing_cols:
            op.add_column("generated_scripts", sa.Column("editor_notes", sa.Text(), nullable=True))

        if "edited_by" not in existing_cols:
            op.add_column("generated_scripts", sa.Column(
                "edited_by", sa.Integer(),
                sa.ForeignKey("console_users.id"),
                nullable=True
            ))

        if "approved_at" not in existing_cols:
            op.add_column("generated_scripts", sa.Column(
                "approved_at", sa.DateTime(timezone=True), nullable=True
            ))


def downgrade() -> None:
    # Remove generated_scripts extensions
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "generated_scripts" in existing_tables:
        existing_cols = [c["name"] for c in inspector.get_columns("generated_scripts")]
        for col in ["approved_at", "edited_by", "editor_notes", "status"]:
            if col in existing_cols:
                op.drop_column("generated_scripts", col)

    op.drop_table("audit_log")
    op.drop_table("upload_targets")
    op.drop_table("template_channel_defaults")
    op.drop_table("channels")
    op.drop_table("platform_credentials")
    op.drop_table("console_users")
