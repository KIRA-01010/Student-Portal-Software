"""Data-access and access rules for teacher-managed StudentRecord / CourseGrade rows.

Who may do what with a record:

  * the **owner** (the teacher who created it) can do everything;
  * a teacher it has been **shared with** can view it and edit its details and
    grades, but cannot delete it, link a portal account or change who else has
    access;
  * an **administrator** can reach every record and do everything, and is the
    only one who can hand a record over to a different owner;
  * every other teacher gets nothing — the record does not even appear to exist.

The one read that is *not* teacher-scoped, `get_for_student`, is keyed on the
signed-in student's own id, so a student can only ever reach the record a
teacher linked to their account.
"""

from typing import List, Optional

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.student_record import CourseGrade, StudentRecord, record_shares
from app.models.course import Course, Enrollment
from app.models.teacher import Teacher
from app.services import student_service, teacher_service
from app.services.exceptions import RecordLinkError, RecordShareError

# Which records a list shows: the teacher's own and shared ones, or (admins only)
# everybody's.
SCOPE_MINE = "mine"
SCOPE_ALL = "all"


# --- Who may do what ------------------------------------------------------------


def is_owner(teacher: Teacher, record: StudentRecord) -> bool:
    return record.created_by_teacher_id == teacher.id


def is_shared_with(teacher: Teacher, record: StudentRecord) -> bool:
    return any(other.id == teacher.id for other in record.shared_with)


def can_manage(teacher: Teacher, record: StudentRecord) -> bool:
    """Manage record identity/linkage. New student records are admin-managed."""
    return teacher.is_admin or (record.linked_student_id is None and is_owner(teacher, record))


def can_manage_grades(teacher: Teacher, record: StudentRecord) -> bool:
    """Add, edit or delete this record's course grades.

    Only the owner, a teacher the record was explicitly shared with, or an
    administrator may touch grades — the same trusted set `can_access`
    documents. Roster-based access (the student is enrolled in one of this
    teacher's *live* courses) only grants a read-only view of the record, so
    that a teacher cannot rewrite grades for courses that were never theirs
    just because the student happens to share one course with them.
    """
    return teacher.is_admin or is_owner(teacher, record) or is_shared_with(teacher, record)


def can_access(db: Session, teacher: Teacher, record: StudentRecord) -> bool:
    """View a record if admin/owner/shared, or if its student is on the teacher's roster."""
    if teacher.is_admin or is_owner(teacher, record) or is_shared_with(teacher, record):
        return True
    if record.linked_student_id is None:
        return False
    return db.scalar(
        select(exists().where(
            Enrollment.student_id == record.linked_student_id,
            Enrollment.course_id == Course.id,
            Course.teacher_id == teacher.id,
        ))
    ) is True


# --- Queries --------------------------------------------------------------------


def list_for_teacher(
    db: Session,
    teacher: Teacher,
    search: Optional[str] = None,
    scope: str = SCOPE_MINE,
) -> List[StudentRecord]:
    """The records `teacher` may see.

    Normally that is the ones they own plus the ones shared with them. An
    administrator asking for ``scope="all"`` gets every record; for anyone else
    that scope is ignored, so it can never widen what an ordinary teacher sees.
    """
    stmt = select(StudentRecord)
    if not (scope == SCOPE_ALL and teacher.is_admin):
        shared_ids = select(record_shares.c.student_record_id).where(
            record_shares.c.teacher_id == teacher.id
        )
        roster_ids = (
            select(Enrollment.student_id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Course.teacher_id == teacher.id)
        )
        stmt = stmt.where(
            or_(
                StudentRecord.created_by_teacher_id == teacher.id,
                StudentRecord.id.in_(shared_ids),
                StudentRecord.linked_student_id.in_(roster_ids),
            )
        )
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(StudentRecord.first_name).like(needle),
                func.lower(StudentRecord.last_name).like(needle),
                func.lower(StudentRecord.registration_number).like(needle),
            )
        )
    stmt = stmt.order_by(StudentRecord.last_name, StudentRecord.first_name)
    return list(db.scalars(stmt).all())


def get_accessible(
    db: Session, teacher: Teacher, record_id: int
) -> Optional[StudentRecord]:
    """The record, only if `teacher` may work on it; otherwise `None`."""
    record = db.get(StudentRecord, record_id)
    if record is None or not can_access(db, teacher, record):
        return None
    return record


def registration_number_exists(db: Session, registration_number: str) -> bool:
    value = registration_number.strip().lower()
    record_exists = db.scalar(
        select(exists().where(func.lower(StudentRecord.registration_number) == value))
    )
    student_exists = db.scalar(
        select(exists().where(func.lower(Student.registration_number) == value))
    )
    return bool(record_exists or student_exists)


def create_record(
    db: Session,
    teacher_id: int,
    *,
    registration_number: str,
    first_name: str,
    last_name: str,
    department: str,
    current_semester: int,
) -> StudentRecord:
    existing_student = student_service.get_by_registration_number(db, registration_number)
    if existing_student is None:
        raise ValueError("Student records are created automatically when an administrator registers a student.")
    if get_for_student(db, existing_student.id) is not None:
        return get_for_student(db, existing_student.id)
    record = StudentRecord(
        registration_number=registration_number,
        first_name=first_name,
        last_name=last_name,
        department=department,
        current_semester=current_semester,
        linked_student_id=existing_student.id,
        created_by_teacher_id=teacher_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_record(
    db: Session,
    record: StudentRecord,
    *,
    first_name: str,
    last_name: str,
    department: str,
    current_semester: int,
) -> StudentRecord:
    if record.linked_student_id is not None:
        raise ValueError("Student academic details are managed by the administrator.")
    record.first_name = first_name
    record.last_name = last_name
    record.department = department
    record.current_semester = current_semester
    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, record: StudentRecord) -> None:
    if record.linked_student_id is not None:
        raise ValueError("Student academic records are managed by the administrator.")
    db.delete(record)
    db.commit()


def add_course_grade(
    db: Session,
    record: StudentRecord,
    *,
    semester: int,
    course_name: str,
    credit_hours: int,
    grade: str,
) -> CourseGrade:
    course_grade = CourseGrade(
        student_record_id=record.id,
        semester=semester,
        course_name=course_name,
        credit_hours=credit_hours,
        grade=grade,
    )
    db.add(course_grade)
    db.commit()
    db.refresh(course_grade)
    return course_grade


def get_course_grade(
    db: Session, record: StudentRecord, course_grade_id: int
) -> Optional[CourseGrade]:
    """A course of `record` (whose access the caller has already checked)."""
    course_grade = db.get(CourseGrade, course_grade_id)
    if course_grade is None or course_grade.student_record_id != record.id:
        return None
    return course_grade


def update_course_grade(
    db: Session,
    course_grade: CourseGrade,
    *,
    semester: int,
    course_name: str,
    credit_hours: int,
    grade: str,
) -> CourseGrade:
    course_grade.semester = semester
    course_grade.course_name = course_name
    course_grade.credit_hours = credit_hours
    course_grade.grade = grade
    db.commit()
    db.refresh(course_grade)
    return course_grade


def delete_course_grade(db: Session, course_grade: CourseGrade) -> None:
    db.delete(course_grade)
    db.commit()


# --- Linking a record to a student account -------------------------------------


def get_for_student(db: Session, student_id: int) -> Optional[StudentRecord]:
    """The record a teacher linked to this student account, if any.

    Takes the student's id (never a record id from the request), so there is
    nothing for a visitor to tamper with to reach someone else's grades.
    """
    stmt = select(StudentRecord).where(StudentRecord.linked_student_id == student_id)
    return db.scalars(stmt).first()


def link_student(db: Session, record: StudentRecord, identifier: str) -> Student:
    """Link `record` to the student account with this registration number or email.

    The caller must already have checked that the teacher owns `record`.
    Linking again to the same account is harmless; linking to a different one
    replaces the old link (the previous student loses access at once).

    Raises:
        RecordLinkError: no such account, or it is already linked to a record.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        raise RecordLinkError("Enter the student's registration number or email address.")

    student = student_service.get_by_registration_number(db, identifier) or student_service.get_by_email(db, identifier)
    if student is None:
        raise RecordLinkError("No student account matches that registration number or email.")

    if record.linked_student_id == student.id:
        return student
    if record.linked_student_id is not None:
        raise RecordLinkError("This student record is already linked to its registered student account.")

    if get_for_student(db, student.id) is not None:
        # Deliberately says nothing about *whose* record it is.
        raise RecordLinkError(
            "That student account is already linked to a student record."
        )

    record.linked_student_id = student.id
    try:
        db.commit()
    except IntegrityError:
        # Two teachers linking the same account at the same moment: the unique
        # index lets exactly one win, and the loser gets the normal message.
        db.rollback()
        raise RecordLinkError(
            "That student account is already linked to a student record."
        )
    db.refresh(record)
    return student


def unlink_student(db: Session, record: StudentRecord) -> None:
    """Remove the link. The student immediately stops seeing this record."""
    if record.linked_student_id is not None:
        record.linked_student_id = None
        db.commit()
        db.refresh(record)


def names_match(record: StudentRecord, student: Student) -> bool:
    """Whether the account's name equals the record's (case-insensitive).

    Used only to warn the teacher about a possible mix-up; names can differ
    legitimately (nicknames, middle names), so a mismatch never blocks a link.
    """

    def normal(first: str, last: str) -> str:
        return " ".join(f"{first} {last}".lower().split())

    return normal(record.first_name, record.last_name) == normal(
        student.first_name, student.last_name
    )


# --- Sharing a record with other teachers ---------------------------------------------


def _find_approved_teacher(db: Session, identifier: str) -> Teacher:
    """Look a colleague up by username or email; only approved teachers count."""
    identifier = (identifier or "").strip()
    if not identifier:
        raise RecordShareError("Enter the teacher's username or email address.")
    teacher = teacher_service.get_by_identifier(db, identifier)
    if teacher is None or not teacher.is_approved:
        # One message for "no such account" and "not approved", so this cannot be
        # used to find out who has registered.
        raise RecordShareError("No approved teacher matches that username or email.")
    return teacher


def share_with(db: Session, record: StudentRecord, identifier: str) -> Teacher:
    """Give another teacher access to `record`.

    The caller must already have checked that the actor may manage the record.
    Sharing again with the same teacher is harmless.

    Raises:
        RecordShareError: nothing to look up, no such approved teacher, or that
            teacher already owns the record.
    """
    teacher = _find_approved_teacher(db, identifier)
    if teacher.id == record.created_by_teacher_id:
        raise RecordShareError("That teacher already owns this record.")
    if not is_shared_with(teacher, record):
        record.shared_with.append(teacher)
        db.commit()
        db.refresh(record)
    return teacher


def unshare(db: Session, record: StudentRecord, teacher_id: int) -> Optional[Teacher]:
    """Take a teacher's access to `record` away. Returns them, or ``None``."""
    for teacher in record.shared_with:
        if teacher.id == teacher_id:
            record.shared_with.remove(teacher)
            db.commit()
            db.refresh(record)
            return teacher
    return None


def transfer_ownership(
    db: Session, actor: Teacher, record: StudentRecord, identifier: str
) -> Teacher:
    """Hand `record` to a different owner (administrators only).

    The previous owner loses all access unless the new owner shares the record
    back. If the new owner already had it shared, that entry is dropped — an
    owner never also appears as a collaborator.
    """
    if not actor.is_admin:
        # Routes already require an admin; this keeps the service safe on its own.
        raise RecordShareError("Only administrators can hand a record to another owner.")
    new_owner = _find_approved_teacher(db, identifier)
    if new_owner.id == record.created_by_teacher_id:
        return new_owner

    record.shared_with = [t for t in record.shared_with if t.id != new_owner.id]
    record.created_by_teacher_id = new_owner.id
    db.commit()
    db.refresh(record)
    return new_owner

