"""Add student semester, course semester and safe course lifecycle state."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    student_cols = {c["name"] for c in insp.get_columns("students")}
    if "current_semester" not in student_cols:
        op.add_column(
            "students",
            sa.Column("current_semester", sa.Integer(), server_default="1", nullable=True),
        )

    # Existing linked records already contain the best available semester. Any
    # legacy/unlinked account gets the safe starting value of semester 1.
    conn.execute(
        sa.text(
            "UPDATE students SET current_semester = COALESCE(("
            "SELECT sr.current_semester FROM student_records sr "
            "WHERE sr.linked_student_id = students.id LIMIT 1"
            "), 1)"
        )
    )
    with op.batch_alter_table("students") as batch:
        batch.alter_column(
            "current_semester",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="1",
        )

    course_cols = {c["name"] for c in sa.inspect(conn).get_columns("courses")}
    if "semester" not in course_cols:
        op.add_column(
            "courses",
            sa.Column("semester", sa.Integer(), server_default="1", nullable=True),
        )
    if "archived" not in course_cols:
        op.add_column(
            "courses",
            sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=True),
        )
    conn.execute(sa.text("UPDATE courses SET semester = COALESCE(semester, 1), archived = COALESCE(archived, 0)"))

    existing_constraints = {c.get("name") for c in sa.inspect(conn).get_unique_constraints("courses")}
    existing_indexes = {i.get("name") for i in sa.inspect(conn).get_indexes("courses")}
    with op.batch_alter_table("courses") as batch:
        batch.alter_column("semester", existing_type=sa.Integer(), nullable=False, server_default="1")
        batch.alter_column("archived", existing_type=sa.Boolean(), nullable=False, server_default="0")
        if "uq_course_offering" not in existing_constraints:
            batch.create_unique_constraint(
                "uq_course_offering",
                ["code", "season", "academic_year", "semester", "department", "entry_type"],
            )
        if "ix_courses_archived" not in existing_indexes:
            batch.create_index("ix_courses_archived", ["archived"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch:
        batch.drop_index("ix_courses_archived")
        batch.drop_constraint("uq_course_offering", type_="unique")
        batch.drop_column("archived")
        batch.drop_column("semester")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("current_semester")
