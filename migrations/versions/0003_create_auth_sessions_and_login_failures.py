"""Create auth_sessions and login_failures tables

Server-side login sessions (so logout really revokes access) and a record of
failed sign-ins (so repeated guessing can be rate-limited).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_sessions_token_hash"), "auth_sessions", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"]
    )
    op.create_index(
        "ix_auth_sessions_role_account_id", "auth_sessions", ["role", "account_id"]
    )

    op.create_table(
        "login_failures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_login_failures_attempted_at"), "login_failures", ["attempted_at"]
    )
    op.create_index(
        "ix_login_failures_role_identifier", "login_failures", ["role", "identifier"]
    )
    op.create_index("ix_login_failures_ip", "login_failures", ["ip"])


def downgrade() -> None:
    op.drop_index("ix_login_failures_ip", table_name="login_failures")
    op.drop_index("ix_login_failures_role_identifier", table_name="login_failures")
    op.drop_index(op.f("ix_login_failures_attempted_at"), table_name="login_failures")
    op.drop_table("login_failures")

    op.drop_index("ix_auth_sessions_role_account_id", table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_expires_at"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_token_hash"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
