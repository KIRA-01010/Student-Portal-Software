"""Allow each student account to be linked to at most one record

Students can now see their own grades through the link a teacher sets in
`student_records.linked_student_id`. This makes the link one-to-one at the
database level, so it can never be ambiguous which record a student sees, even
if two teachers try to link the same account at the same moment.

The column was never settable before this release, so every existing value is
NULL and the unique index (which allows any number of NULLs) cannot conflict.

The index is only created when missing, so the migration also succeeds on a
database whose tables were built straight from the current models.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_student_records_linked_student_id"


def _existing_index_names() -> set:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes("student_records")}


def upgrade() -> None:
    if INDEX_NAME not in _existing_index_names():
        op.create_index(INDEX_NAME, "student_records", ["linked_student_id"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="student_records")
