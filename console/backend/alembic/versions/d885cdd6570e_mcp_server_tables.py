"""mcp server tables

Revision ID: d885cdd6570e
Revises: 021
Create Date: 2026-05-09 20:01:56.269063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd885cdd6570e'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. audit_log.actor_metadata
    op.add_column(
        "audit_log",
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. mcp_api_keys
    op.create_table(
        "mcp_api_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("service_user_id", sa.Integer, sa.ForeignKey("console_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mcp_api_keys_key_hash", "mcp_api_keys", ["key_hash"])

    # 3. mcp_tool_calls
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("transport", sa.Text, nullable=False),
        sa.Column("actor_jwt_sub", sa.Text, nullable=True),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=True),
        sa.Column("args_redacted", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ok", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("task_id", sa.Text, nullable=True),
    )
    op.create_index("ix_mcp_tool_calls_called_at", "mcp_tool_calls", ["called_at"])
    op.create_index("ix_mcp_tool_calls_tool_name", "mcp_tool_calls", ["tool_name"])

    # 4. seed mcp-system user (login disabled via unusable bcrypt hash)
    op.execute(
        """
        INSERT INTO console_users (username, email, password_hash, role, created_at)
        VALUES ('mcp-system', 'mcp-system@local', '!disabled!', 'admin', now())
        ON CONFLICT (username) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM console_users WHERE username = 'mcp-system'")
    op.drop_index("ix_mcp_tool_calls_tool_name", table_name="mcp_tool_calls")
    op.drop_index("ix_mcp_tool_calls_called_at", table_name="mcp_tool_calls")
    op.drop_table("mcp_tool_calls")
    op.drop_index("ix_mcp_api_keys_key_hash", table_name="mcp_api_keys")
    op.drop_table("mcp_api_keys")
    op.drop_column("audit_log", "actor_metadata")
