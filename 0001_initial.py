"""initial schema: users, command_history, refresh_sessions

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-12

This mirrors backend/models.py. After this lands, prefer
`alembic revision --autogenerate` for future schema changes instead of
the dev-only init_models() auto-create.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "command_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", sa.String(512), nullable=False),
        sa.Column("module", sa.String(64), nullable=True),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("ok", sa.Boolean, server_default=sa.true()),
        sa.Column("duration_ms", sa.Float, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_history_user", "command_history", ["user_id"])
    op.create_index("ix_history_created", "command_history", ["created_at"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_token", "refresh_sessions", ["token_id"])


def downgrade() -> None:
    op.drop_table("refresh_sessions")
    op.drop_table("command_history")
    op.drop_table("users")
