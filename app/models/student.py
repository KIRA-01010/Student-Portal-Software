"""Student ORM model."""

from app.database.base import Base
from app.models.account import AccountMixin
from sqlalchemy import Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column


class Student(Base, AccountMixin):
    """An administrator-created student account and academic identity."""

    __tablename__ = "students"

    # Immutable institutional identity. Username remains in the legacy schema
    # only for backwards compatibility; students authenticate by this number.
    registration_number: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=True)
    department: Mapped[str] = mapped_column(String(120), nullable=True)
    season: Mapped[str] = mapped_column(String(10), nullable=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=True)
    current_semester: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=True)

    # A student has exactly one academic record. It is created automatically
    # when the administrator creates the student account.
    academic_record = relationship(
        "StudentRecord",
        back_populates="linked_student",
        uselist=False,
        foreign_keys="StudentRecord.linked_student_id",
    )
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan")
