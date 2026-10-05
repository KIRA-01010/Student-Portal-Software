"""ORM models. Import them here so Alembic autogenerate sees every table."""

from app.models.security import AuthSession, LoginFailure
from app.models.course import Assignment, Course, Enrollment, Submission
from app.models.student import Student
from app.models.student_record import CourseGrade, StudentRecord, record_shares
from app.models.teacher import Teacher, TeacherStatus

__all__ = [
    "Student",
    "Teacher",
    "TeacherStatus",
    "StudentRecord",
    "CourseGrade",
    "record_shares",
    "AuthSession",
    "LoginFailure",
    "Course",
    "Enrollment",
    "Assignment",
    "Submission",
]
