"""Administrator-managed Student account data access."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.student_record import StudentRecord
from app.services.account_repository import AccountRepository
from app.utils.security import hash_password


class StudentAccountRepository(AccountRepository[Student]):
    """Student login uses the institutional registration number, not username."""

    def get_by_identifier(self, db: Session, identifier: str) -> Optional[Student]:
        value = identifier.strip()
        stmt = select(Student).where(Student.registration_number == value)
        return db.scalars(stmt).first()


repository = StudentAccountRepository(Student)

get_by_id = repository.get_by_id
get_by_email = repository.get_by_email
get_by_username = repository.get_by_username
get_by_identifier = repository.get_by_identifier
email_exists = repository.email_exists
username_exists = repository.username_exists
touch_last_login = repository.touch_last_login


def get_by_registration_number(db: Session, registration_number: str) -> Optional[Student]:
    return db.scalar(select(Student).where(Student.registration_number == registration_number.strip()))


def registration_number_exists(db: Session, registration_number: str) -> bool:
    return get_by_registration_number(db, registration_number) is not None


def create_admin_student(
    db: Session,
    *,
    registration_number: str,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    department: str,
    season: str,
    academic_year: int,
    entry_type: str,
    current_semester: int,
    created_by_teacher_id: int,
) -> Student:
    """Create a student account. Only the admin route should call this."""
    student = Student(
        registration_number=registration_number,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        # Legacy compatibility only; students never see/use this field.
        username=registration_number,
        email=email.strip().lower(),
        password_hash=hash_password(password),
        department=department.strip(),
        season=season,
        academic_year=academic_year,
        current_semester=current_semester,
        entry_type=entry_type,
    )
    db.add(student)
    db.flush()

    # The academic record is created as part of the same transaction, so a
    # student account can never be committed without its record.
    record = StudentRecord(
        registration_number=registration_number,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        department=department.strip(),
        current_semester=current_semester,
        linked_student_id=student.id,
        created_by_teacher_id=created_by_teacher_id,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(student)
    return student


def list_students(db: Session):
    return list(db.scalars(select(Student).order_by(Student.last_name, Student.first_name, Student.registration_number)).all())
