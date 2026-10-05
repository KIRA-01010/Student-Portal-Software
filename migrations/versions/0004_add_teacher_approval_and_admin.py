"""Add teacher approval status and an admin flag

Teacher sign-up was open to anyone, and every teacher account could create
academic records. From now on a new teacher account is ``pending`` until an
administrator approves it, and administrators are teachers with ``is_admin``.

Existing teachers are marked ``approved`` so nobody is locked out by the
upgrade. Nobody becomes an administrator automatically: promote an account from
the command line with ``python -m app.cli promote <username>``, and review the
list with ``python -m app.cli list``.

The columns are only added when missing, so the migration also succeeds on a
database whose tables were built straight from the current models (the old
``create_all()`` start-up path).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _teacher_columns() -> set:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("teachers")}


def upgrade() -> None:
    existing = _teacher_columns()

    if "status" not in existing:
        # The column default is "pending" (fail closed for any future insert
        # that forgets to say), but every teacher that already exists was let
        # in under the old rules, so they start out approved.
        op.add_column(
            "teachers",
            sa.Column(
                "status", sa.String(length=10), nullable=False, server_default="pending"
            ),
        )
        op.execute("UPDATE teachers SET status = 'approved'")

    if "is_admin" not in existing:
        op.add_column(
            "teachers",
            sa.Column(
                "is_admin", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )

    if "reviewed_at" not in existing:
        op.add_column(
            "teachers",
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "reviewed_by_id" not in existing:
        op.add_column(
            "teachers", sa.Column("reviewed_by_id", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    # Batch mode: SQLite cannot drop columns in place on older versions.
    with op.batch_alter_table("teachers") as batch:
        batch.drop_column("reviewed_by_id")
        batch.drop_column("reviewed_at")
        batch.drop_column("is_admin")
        batch.drop_column("status")
