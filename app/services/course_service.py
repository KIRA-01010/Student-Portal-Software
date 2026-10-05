"""Access rules and data operations for the live course catalog and assignments."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.course import Assignment, Course, Enrollment, Submission
from app.models.student import Student
from app.utils.clock import as_utc

ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def create_course(db: Session, *, name: str, code: str, description: str = "", season: str, academic_year: int, semester: int, department: str, entry_type: str) -> Course:
    course = Course(
        name=name.strip(), code=code.strip().upper(), description=description.strip() or None,
        season=season, academic_year=academic_year, semester=semester, department=department.strip(), entry_type=entry_type,
        teacher_id=None, archived=False,
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A course with the same code and academic offering already exists.")
    db.refresh(course)
    return course


def matching_students(db: Session, *, season: str, academic_year: int, semester: int, department: str):
    """Students whose season/year/semester/department place them in this course's offering."""
    stmt = select(Student).where(
        Student.season == season,
        Student.academic_year == academic_year,
        Student.current_semester == semester,
        Student.department == department,
    )
    return list(db.scalars(stmt).all())


def enroll_matching_students(db: Session, course: Course) -> int:
    """Enroll every student in `course`'s offering (season/year/semester/department).

    Called right after a course is added to the catalog, so students already
    registered under that offering are picked up immediately. Already-enrolled
    students are left alone (`enroll_student` is idempotent). Returns how many
    enrollments were newly created.
    """
    if course.archived:
        return 0
    students = matching_students(
        db,
        season=course.season,
        academic_year=course.academic_year,
        semester=course.semester,
        department=course.department,
    )
    created = 0
    for student in students:
        existing = db.scalar(
            select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student.id)
        )
        enroll_student(db, course, student.id)
        if existing is None:
            created += 1
    return created


def enroll_student_in_matching_courses(db: Session, student: Student) -> int:
    """Enroll `student` in every active course in their season/year/semester/department offering.

    Called right after a student account is created (or their offering fields
    are edited), so they land on every course an admin already set up for
    that category without a teacher adding them by hand. Only replaces the
    manual "add students one by one" step — a teacher can still enroll or
    remove individual students afterward.
    """
    stmt = select(Course).where(
        Course.season == student.season,
        Course.academic_year == student.academic_year,
        Course.semester == student.current_semester,
        Course.department == student.department,
        Course.archived.is_(False),
    )
    courses = list(db.scalars(stmt).all())
    created = 0
    for course in courses:
        existing = db.scalar(
            select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student.id)
        )
        enroll_student(db, course, student.id)
        if existing is None:
            created += 1
    return created


def available_courses(db: Session):
    return list(db.scalars(
        select(Course).where(Course.teacher_id.is_(None), Course.archived.is_(False))
        .order_by(Course.academic_year.desc(), Course.semester, Course.name)
    ).all())


def courses_for_teacher(db: Session, teacher_id: int):
    return list(db.scalars(
        select(Course).where(Course.teacher_id == teacher_id)
        .options(joinedload(Course.enrollments).joinedload(Enrollment.student))
        .order_by(Course.archived, Course.academic_year.desc(), Course.semester, Course.name)
    ).unique().all())


def claim_course(db: Session, teacher_id: int, course_id: int) -> Optional[Course]:
    """Atomically claim an unassigned, active course so two teachers cannot take it."""
    result = db.execute(
        update(Course)
        .where(Course.id == course_id, Course.teacher_id.is_(None), Course.archived.is_(False))
        .values(teacher_id=teacher_id)
    )
    if result.rowcount != 1:
        db.rollback()
        course = db.get(Course, course_id)
        if course is not None and course.teacher_id == teacher_id:
            return course
        return None
    db.commit()
    return db.get(Course, course_id)


def release_course(db: Session, teacher_id: int, course_id: int) -> bool:
    """Atomically release a course owned by this teacher."""
    result = db.execute(
        update(Course)
        .where(Course.id == course_id, Course.teacher_id == teacher_id)
        .values(teacher_id=None)
    )
    db.commit()
    return result.rowcount == 1


def get_teacher_course(db: Session, teacher_id: int, course_id: int) -> Optional[Course]:
    return db.scalar(select(Course).where(Course.id == course_id, Course.teacher_id == teacher_id))


def get_course(db: Session, course_id: int) -> Optional[Course]:
    return db.get(Course, course_id)


def course_counts(db: Session, course_id: int) -> tuple[int, int]:
    students = db.scalar(select(func.count(Enrollment.id)).where(Enrollment.course_id == course_id)) or 0
    assignments = db.scalar(select(func.count(Assignment.id)).where(Assignment.course_id == course_id)) or 0
    return students, assignments


def delete_course(db: Session, course_id: int) -> bool:
    """Permanently delete only a course with no dependent data."""
    students, assignments = course_counts(db, course_id)
    if students or assignments:
        return False
    course = db.get(Course, course_id)
    if course is None:
        return False
    db.delete(course)
    db.commit()
    return True


def archive_course(db: Session, course_id: int) -> Optional[Course]:
    course = db.get(Course, course_id)
    if course is None:
        return None
    course.archived = True
    db.commit(); db.refresh(course)
    return course


def restore_course(db: Session, course_id: int) -> Optional[Course]:
    course = db.get(Course, course_id)
    if course is None:
        return None
    course.archived = False
    db.commit(); db.refresh(course)
    return course


def enroll_student(db: Session, course: Course, student_id: int) -> Enrollment:
    if course.archived:
        raise ValueError("Archived courses cannot receive new students.")
    existing = db.scalar(select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id))
    if existing:
        return existing
    enrollment = Enrollment(course_id=course.id, student_id=student_id)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id))
        if existing:
            return existing
        raise
    db.refresh(enrollment)
    return enrollment


def unenroll_student(db: Session, course: Course, student_id: int) -> None:
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id))
    if row:
        db.delete(row); db.commit()


def students_in_course(db: Session, course_id: int):
    stmt = select(Student).join(Enrollment, Enrollment.student_id == Student.id).where(Enrollment.course_id == course_id).order_by(Student.last_name, Student.first_name)
    return list(db.scalars(stmt).all())


def all_students(db: Session):
    return list(db.scalars(select(Student).order_by(Student.last_name, Student.first_name, Student.registration_number)).all())


def create_assignment(db: Session, course: Course, title: str, description: str, deadline: datetime) -> Assignment:
    if course.archived:
        raise ValueError("Archived courses cannot receive new assignments.")
    assignment = Assignment(course_id=course.id, title=title.strip(), description=description.strip() or None, deadline=deadline)
    db.add(assignment); db.commit(); db.refresh(assignment)
    return assignment


def assignments_for_teacher(db: Session, teacher_id: int):
    stmt = select(Assignment).join(Course).where(Course.teacher_id == teacher_id).options(joinedload(Assignment.course), joinedload(Assignment.submissions)).order_by(Assignment.deadline.desc(), Assignment.id.desc())
    return list(db.scalars(stmt).unique().all())


def assignments_for_student(db: Session, student_id: int):
    stmt = (select(Assignment).join(Course).join(Enrollment, Enrollment.course_id == Course.id)
            .where(Enrollment.student_id == student_id, Course.archived.is_(False)).options(joinedload(Assignment.course), joinedload(Assignment.submissions))
            .order_by(Assignment.deadline.asc(), Assignment.id.desc()))
    return list(db.scalars(stmt).unique().all())


def get_student_assignment(db: Session, student_id: int, assignment_id: int) -> Optional[Assignment]:
    stmt = (select(Assignment).join(Course).join(Enrollment, Enrollment.course_id == Course.id)
            .where(Assignment.id == assignment_id, Enrollment.student_id == student_id, Course.archived.is_(False))
            .options(joinedload(Assignment.course), joinedload(Assignment.submissions)))
    return db.scalars(stmt).unique().first()


def get_teacher_assignment(db: Session, teacher_id: int, assignment_id: int) -> Optional[Assignment]:
    stmt = select(Assignment).join(Course).where(Assignment.id == assignment_id, Course.teacher_id == teacher_id).options(joinedload(Assignment.course), joinedload(Assignment.submissions).joinedload(Submission.student))
    return db.scalars(stmt).unique().first()


def get_submission(submissions, student_id: int) -> Optional[Submission]:
    return next((s for s in submissions if s.student_id == student_id), None)


def save_submission(db: Session, assignment: Assignment, student_id: int, original_filename: str, content_type: str, content: bytes, upload_dir: Path) -> Submission:
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF and common image files are allowed.")
    if content_type not in ALLOWED_TYPES and content_type != "application/octet-stream":
        raise ValueError("Only PDF and common image files are allowed.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("The file is too large. Maximum size is 10 MB.")

    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    (upload_dir / filename).write_bytes(content)

    submission = db.scalar(select(Submission).where(Submission.assignment_id == assignment.id, Submission.student_id == student_id))
    now = datetime.now(timezone.utc)
    late = now > as_utc(assignment.deadline)
    if submission:
        old = upload_dir / submission.stored_filename
        if old.exists(): old.unlink()
        submission.original_filename = original_filename
        submission.stored_filename = filename
        submission.content_type = content_type
        submission.file_size = len(content)
        submission.submitted_at = now
        submission.late = late
    else:
        submission = Submission(assignment_id=assignment.id, student_id=student_id, original_filename=original_filename, stored_filename=filename, content_type=content_type, file_size=len(content), submitted_at=now, late=late)
        db.add(submission)
    db.commit(); db.refresh(submission)
    return submission
