"""Add admin-managed student identity fields and admin-owned course catalog."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    student_cols = {c["name"] for c in insp.get_columns("students")}
    new_student_cols = {
        "registration_number": sa.Column("registration_number", sa.String(8), nullable=True),
        "department": sa.Column("department", sa.String(120), nullable=True),
        "season": sa.Column("season", sa.String(10), nullable=True),
        "academic_year": sa.Column("academic_year", sa.Integer(), nullable=True),
        "entry_type": sa.Column("entry_type", sa.String(10), nullable=True),
    }
    for name, column in new_student_cols.items():
        if name not in student_cols:
            op.add_column("students", column)

    # Give existing accounts a deterministic institutional identifier so the
    # migration does not strand demo accounts. New accounts use an 8-digit value
    # chosen by the administrator.
    existing_students = conn.execute(
        sa.text("SELECT id FROM students WHERE registration_number IS NULL ORDER BY id")
    ).fetchall()
    if existing_students:
        conn.execute(
            sa.text("UPDATE students SET registration_number=:reg, department=COALESCE(department,'Unassigned'), season=COALESCE(season,'Fall'), academic_year=COALESCE(academic_year,2026), entry_type=COALESCE(entry_type,'Regular') WHERE id=:id AND registration_number IS NULL"),
            [{"reg": f"{row.id:08d}", "id": row.id} for row in existing_students],
        )
    conn.execute(sa.text("UPDATE students SET username=registration_number WHERE registration_number IS NOT NULL"))

    if not any(i.get("name") == "ix_students_registration_number" for i in sa.inspect(conn).get_indexes("students")):
        op.create_index("ix_students_registration_number", "students", ["registration_number"], unique=True)

    course_cols = {c["name"] for c in sa.inspect(conn).get_columns("courses")}
    new_course_cols = {
        "season": sa.Column("season", sa.String(10), nullable=True),
        "academic_year": sa.Column("academic_year", sa.Integer(), nullable=True),
        "department": sa.Column("department", sa.String(120), nullable=True),
        "entry_type": sa.Column("entry_type", sa.String(10), nullable=True),
    }
    for name, column in new_course_cols.items():
        if name not in course_cols:
            op.add_column("courses", column)

    conn.execute(sa.text("UPDATE courses SET season=COALESCE(season,'Fall'), academic_year=COALESCE(academic_year,2026), department=COALESCE(department,'General'), entry_type=COALESCE(entry_type,'Regular')"))

    # teacher_id is nullable so an admin can publish a catalog item before any
    # teacher claims it. Use Alembic's batch mode for SQLite compatibility.
    with op.batch_alter_table("courses") as batch:
        batch.alter_column("teacher_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("season", existing_type=sa.String(10), nullable=False)
        batch.alter_column("academic_year", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("department", existing_type=sa.String(120), nullable=False)
        batch.alter_column("entry_type", existing_type=sa.String(10), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch:
        batch.alter_column("teacher_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("entry_type")
        batch.drop_column("department")
        batch.drop_column("academic_year")
        batch.drop_column("season")
    if any(i.get("name") == "ix_students_registration_number" for i in sa.inspect(op.get_bind()).get_indexes("students")):
        op.drop_index("ix_students_registration_number", table_name="students")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("entry_type")
        batch.drop_column("academic_year")
        batch.drop_column("season")
        batch.drop_column("department")
        batch.drop_column("registration_number")
