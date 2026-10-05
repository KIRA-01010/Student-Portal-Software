"""Create teachers, student_records and course_grades tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_teachers_email"), "teachers", ["email"], unique=True)
    op.create_index(op.f("ix_teachers_username"), "teachers", ["username"], unique=True)

    op.create_table(
        "student_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registration_number", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("current_semester", sa.Integer(), nullable=False),
        sa.Column("linked_student_id", sa.Integer(), nullable=True),
        sa.Column("created_by_teacher_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["linked_student_id"], ["students.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_teacher_id"], ["teachers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_student_records_registration_number"),
        "student_records",
        ["registration_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_student_records_created_by_teacher_id"),
        "student_records",
        ["created_by_teacher_id"],
        unique=False,
    )

    op.create_table(
        "course_grades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_record_id", sa.Integer(), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("course_name", sa.String(length=150), nullable=False),
        sa.Column("credit_hours", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(length=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_record_id"], ["student_records.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_course_grades_student_record_id"),
        "course_grades",
        ["student_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_course_grades_student_record_id"), table_name="course_grades")
    op.drop_table("course_grades")

    op.drop_index(
        op.f("ix_student_records_created_by_teacher_id"), table_name="student_records"
    )
    op.drop_index(
        op.f("ix_student_records_registration_number"), table_name="student_records"
    )
    op.drop_table("student_records")

    op.drop_index(op.f("ix_teachers_username"), table_name="teachers")
    op.drop_index(op.f("ix_teachers_email"), table_name="teachers")
    op.drop_table("teachers")
