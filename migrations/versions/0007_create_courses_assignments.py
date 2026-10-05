"""Create live courses, enrollments, assignments and submissions."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("courses"):
        op.create_table(
            "courses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("code", sa.String(30), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("teacher_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_courses_teacher_id", "courses", ["teacher_id"])
    if not insp.has_table("course_enrollments"):
        op.create_table(
            "course_enrollments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("course_id", "student_id", name="uq_course_student"),
        )
        op.create_index("ix_course_enrollments_course_id", "course_enrollments", ["course_id"])
        op.create_index("ix_course_enrollments_student_id", "course_enrollments", ["student_id"])
    if not insp.has_table("assignments"):
        op.create_table(
            "assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_assignments_course_id", "assignments", ["course_id"])
        op.create_index("ix_assignments_deadline", "assignments", ["deadline"])
    if not insp.has_table("assignment_submissions"):
        op.create_table(
            "assignment_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assignment_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("late", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
        )
        op.create_index("ix_assignment_submissions_assignment_id", "assignment_submissions", ["assignment_id"])
        op.create_index("ix_assignment_submissions_student_id", "assignment_submissions", ["student_id"])
        op.create_index("ix_assignment_submissions_submitted_at", "assignment_submissions", ["submitted_at"])


def downgrade() -> None:
    op.drop_table("assignment_submissions")
    op.drop_table("assignments")
    op.drop_table("course_enrollments")
    op.drop_table("courses")
