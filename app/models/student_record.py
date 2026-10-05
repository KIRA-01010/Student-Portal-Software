"""Academic records and course grades associated with student accounts.

A current student record is created automatically with the administrator-created
`Student` account and is linked one-to-one through `linked_student_id`. The
legacy teacher-owner/share fields remain for older migrated records so existing
grade data is not lost.
"""

from typing import List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

# Teachers a record has been shared with, besides the teacher who owns it.
# A plain association table: sharing carries no data beyond "may work on this".
# The owner is *not* stored here — `created_by_teacher_id` says who owns it.
record_shares = Table(
    "record_shares",
    Base.metadata,
    Column(
        "student_record_id",
        Integer,
        ForeignKey("student_records.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "teacher_id",
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class StudentRecord(Base, TimestampMixin):
    """A student's academic profile and grade container.

    New records are created by the administrator at student registration and
    are linked one-to-one to the student account. `created_by_teacher_id` and
    sharing are retained for backwards compatibility with pre-existing records.
    """

    __tablename__ = "student_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    registration_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    current_semester: Mapped[int] = mapped_column(Integer, nullable=False)

    # Unique: a student account sees exactly one record, so it can never be
    # ambiguous which one. (Many rows may be NULL — unlinked records.)
    linked_student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_by_teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    linked_student: Mapped[Optional["Student"]] = relationship(
        "Student", back_populates="academic_record", foreign_keys=[linked_student_id]
    )

    owner: Mapped["Teacher"] = relationship(
        "Teacher", foreign_keys="StudentRecord.created_by_teacher_id"
    )
    shared_with: Mapped[List["Teacher"]] = relationship(
        "Teacher",
        secondary=record_shares,
        order_by="Teacher.last_name, Teacher.first_name, Teacher.id",
    )

    course_grades: Mapped[List["CourseGrade"]] = relationship(
        back_populates="student_record",
        cascade="all, delete-orphan",
        order_by="CourseGrade.semester, CourseGrade.id",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_linked(self) -> bool:
        return self.linked_student_id is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<StudentRecord id={self.id} "
            f"registration_number={self.registration_number!r}>"
        )


class CourseGrade(Base, TimestampMixin):
    """One course/subject result contributing to a student's CGPA."""

    __tablename__ = "course_grades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    student_record_id: Mapped[int] = mapped_column(
        ForeignKey("student_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    course_name: Mapped[str] = mapped_column(String(150), nullable=False)
    credit_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(2), nullable=False)

    student_record: Mapped["StudentRecord"] = relationship(
        back_populates="course_grades"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CourseGrade id={self.id} course_name={self.course_name!r}>"
