"""Let a student record be shared with other teachers

A record belonged to exactly one teacher, so two teachers could never work with
the same student. This adds an association table listing the extra teachers who
may view and edit a record; the owner stays in
`student_records.created_by_teacher_id` and keeps the owner-only actions
(delete, link a portal account, share).

Nothing is shared automatically, so upgrading changes nobody's access.

The table is only created when missing, so the migration also succeeds on a
database whose tables were built straight from the current models (the old
``create_all()`` start-up path).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("record_shares"):
        return

    op.create_table(
        "record_shares",
        sa.Column("student_record_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_record_id"], ["student_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("student_record_id", "teacher_id"),
    )
    op.create_index(
        op.f("ix_record_shares_teacher_id"),
        "record_shares",
        ["teacher_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_record_shares_teacher_id"), table_name="record_shares")
    op.drop_table("record_shares")
