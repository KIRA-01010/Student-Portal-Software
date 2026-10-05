"""Live course catalog, enrollments, assignments and student submissions."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.utils.clock import utcnow


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint(
            "code", "season", "academic_year", "semester", "department", "entry_type",
            name="uq_course_offering",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False, index=True)
    # One Course row has one teacher slot. NULL means the admin-created course
    # is still available for a teacher to claim.
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)

    teacher = relationship("Teacher", back_populates="courses")
    enrollments: Mapped[List["Enrollment"]] = relationship(cascade="all, delete-orphan", back_populates="course")
    assignments: Mapped[List["Assignment"]] = relationship(cascade="all, delete-orphan", back_populates="course", order_by="Assignment.deadline")


class Enrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="enrollments")
    student = relationship("Student", back_populates="enrollments")


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    course: Mapped["Course"] = relationship(back_populates="assignments")
    submissions: Mapped[List["Submission"]] = relationship(cascade="all, delete-orphan", back_populates="assignment")


class Submission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student = relationship("Student", back_populates="submissions")

    @property
    def status(self) -> str:
        return "Late" if self.late else "On time"
