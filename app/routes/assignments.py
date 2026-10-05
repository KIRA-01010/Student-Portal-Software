"""Student and teacher assignment workflows."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from app.config import settings
from app.database.session import get_db
from app.models.course import Assignment
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import course_service
from app.utils.dependencies import require_student, require_teacher, verify_csrf
from app.utils.templating import flash, render
from app.utils.clock import as_utc

student_router = APIRouter(tags=["assignments"])
teacher_router = APIRouter(prefix="/teacher", tags=["teacher-assignments"])


def _parse_deadline(value: str) -> datetime:
    try:
        # The portal's form is intended for Pakistan local time (UTC+05:00),
        # then normalized to UTC for storage/comparison.
        pakistan_tz = timezone(timedelta(hours=5))
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=pakistan_tz).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError("Enter a valid deadline.") from exc


@student_router.get("/assignments", name="assignments_page")
def assignments_page(request: Request, student: Student = Depends(require_student), db: Session = Depends(get_db)):
    assignments = course_service.assignments_for_student(db, student.id)
    now = datetime.now(timezone.utc)
    for a in assignments:
        a.student_submission = course_service.get_submission(a.submissions, student.id)
        a.is_overdue = now > as_utc(a.deadline)
    return render(request, "dashboard/assignments.html", {"student": student, "assignments": assignments, "now": now})


@student_router.get("/assignments/{assignment_id}", name="student_assignment_detail")
def student_assignment_detail(request: Request, assignment_id: int, student: Student = Depends(require_student), db: Session = Depends(get_db)):
    assignment = course_service.get_student_assignment(db, student.id, assignment_id)
    if assignment is None:
        raise StarletteHTTPException(status_code=404)
    submission = course_service.get_submission(assignment.submissions, student.id)
    assignment.is_overdue = datetime.now(timezone.utc) > as_utc(assignment.deadline)
    return render(request, "dashboard/assignment_detail.html", {"student": student, "assignment": assignment, "submission": submission, "now": datetime.now(timezone.utc)})


@student_router.post("/assignments/{assignment_id}/submit", name="student_assignment_submit")
async def student_assignment_submit(request: Request, assignment_id: int, file: UploadFile = File(...), student: Student = Depends(require_student), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    assignment = course_service.get_student_assignment(db, student.id, assignment_id)
    if assignment is None:
        raise StarletteHTTPException(status_code=404)
    content = await file.read()
    try:
        course_service.save_submission(db, assignment, student.id, file.filename or "submission", file.content_type or "application/octet-stream", content, settings.upload_dir)
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(request.url_for("student_assignment_detail", assignment_id=assignment_id), status_code=HTTP_303_SEE_OTHER)
    is_late = datetime.now(timezone.utc) > as_utc(assignment.deadline)
    flash(request, "Assignment submitted successfully." + (" It was marked late." if is_late else ""), "warning" if is_late else "success")
    return RedirectResponse(request.url_for("student_assignment_detail", assignment_id=assignment_id), status_code=HTTP_303_SEE_OTHER)


@student_router.get("/assignments/{assignment_id}/submission", name="student_submission_file")
def student_submission_file(assignment_id: int, student: Student = Depends(require_student), db: Session = Depends(get_db)):
    assignment = course_service.get_student_assignment(db, student.id, assignment_id)
    if assignment is None:
        raise StarletteHTTPException(status_code=404)
    submission = course_service.get_submission(assignment.submissions, student.id)
    if submission is None:
        raise StarletteHTTPException(status_code=404)
    path = settings.upload_dir / submission.stored_filename
    if not path.exists():
        raise StarletteHTTPException(status_code=404)
    return FileResponse(path, media_type=submission.content_type, filename=submission.original_filename)


# ---------------- teacher courses ----------------
@teacher_router.get("/courses", name="teacher_courses_page")
def teacher_courses_page(request: Request, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db)):
    courses = course_service.courses_for_teacher(db, teacher.id)
    available = course_service.available_courses(db)
    students = course_service.all_students(db)
    return render(request, "teacher/courses.html", {"teacher": teacher, "courses": courses, "available_courses": available, "students": students})


@teacher_router.post("/courses/{course_id}/release", name="teacher_course_release")
def teacher_course_release(request: Request, course_id: int, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    if course_service.release_course(db, teacher.id, course_id):
        flash(request, "Course released. It is now available for another teacher to claim.", "info")
    else:
        raise StarletteHTTPException(status_code=404)
    return RedirectResponse(request.url_for("teacher_courses_page"), status_code=HTTP_303_SEE_OTHER)


@teacher_router.post("/courses/{course_id}/claim", name="teacher_course_claim")
def teacher_course_claim(request: Request, course_id: int, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    claimed = course_service.claim_course(db, teacher.id, course_id)
    if claimed is None:
        flash(request, "That course has already been assigned to another teacher.", "warning")
    else:
        flash(request, f"You are now assigned to {claimed.code} — {claimed.name}.", "success")
    return RedirectResponse(request.url_for("teacher_courses_page"), status_code=HTTP_303_SEE_OTHER)


@teacher_router.post("/courses/{course_id}/enroll", name="teacher_course_enroll")
def teacher_course_enroll(request: Request, course_id: int, student_id: int = Form(...), teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    course = course_service.get_teacher_course(db, teacher.id, course_id)
    if course is None:
        raise StarletteHTTPException(status_code=404)
    if db.get(Student, student_id) is None:
        raise StarletteHTTPException(status_code=404)
    try:
        course_service.enroll_student(db, course, student_id)
    except ValueError as exc:
        flash(request, str(exc), "warning")
    else:
        flash(request, "Student enrolled in the course.", "success")
    return RedirectResponse(request.url_for("teacher_courses_page"), status_code=HTTP_303_SEE_OTHER)


@teacher_router.post("/courses/{course_id}/unenroll", name="teacher_course_unenroll")
def teacher_course_unenroll(request: Request, course_id: int, student_id: int = Form(...), teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    course = course_service.get_teacher_course(db, teacher.id, course_id)
    if course is None:
        raise StarletteHTTPException(status_code=404)
    course_service.unenroll_student(db, course, student_id)
    flash(request, "Student removed from the course.", "info")
    return RedirectResponse(request.url_for("teacher_courses_page"), status_code=HTTP_303_SEE_OTHER)


# ---------------- teacher assignments ----------------
@teacher_router.get("/assignments", name="teacher_assignments_page")
def teacher_assignments_page(request: Request, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db)):
    assignments = course_service.assignments_for_teacher(db, teacher.id)
    courses = course_service.courses_for_teacher(db, teacher.id)
    for a in assignments:
        a.submission_count = len(a.submissions)
        a.is_overdue = datetime.now(timezone.utc) > as_utc(a.deadline)
    return render(request, "teacher/assignments.html", {"teacher": teacher, "assignments": assignments, "courses": courses, "now": datetime.now(timezone.utc)})


@teacher_router.post("/assignments", name="teacher_assignment_create")
def teacher_assignment_create(request: Request, course_id: int = Form(...), title: str = Form(""), description: str = Form(""), deadline: str = Form(""), teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db), __: None = Depends(verify_csrf)):
    course = course_service.get_teacher_course(db, teacher.id, course_id)
    if course is None:
        raise StarletteHTTPException(status_code=404)
    try:
        parsed = _parse_deadline(deadline)
        if not title.strip():
            raise ValueError("Assignment title is required.")
        course_service.create_assignment(db, course, title, description, parsed)
        flash(request, "Assignment created and published to enrolled students.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(request.url_for("teacher_assignments_page"), status_code=HTTP_303_SEE_OTHER)


@teacher_router.get("/assignments/{assignment_id}", name="teacher_assignment_detail")
def teacher_assignment_detail(request: Request, assignment_id: int, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db)):
    assignment = course_service.get_teacher_assignment(db, teacher.id, assignment_id)
    if assignment is None:
        raise StarletteHTTPException(status_code=404)
    enrolled = course_service.students_in_course(db, assignment.course_id)
    assignment.is_overdue = datetime.now(timezone.utc) > as_utc(assignment.deadline)
    return render(request, "teacher/assignment_detail.html", {"teacher": teacher, "assignment": assignment, "enrolled": enrolled, "now": datetime.now(timezone.utc)})


@teacher_router.get("/assignments/{assignment_id}/submissions/{submission_id}/file", name="teacher_submission_file")
def teacher_submission_file(assignment_id: int, submission_id: int, teacher: Teacher = Depends(require_teacher), db: Session = Depends(get_db)):
    assignment = course_service.get_teacher_assignment(db, teacher.id, assignment_id)
    if assignment is None:
        raise StarletteHTTPException(status_code=404)
    submission = next((s for s in assignment.submissions if s.id == submission_id), None)
    if submission is None:
        raise StarletteHTTPException(status_code=404)
    path = settings.upload_dir / submission.stored_filename
    if not path.exists():
        raise StarletteHTTPException(status_code=404)
    return FileResponse(path, media_type=submission.content_type, filename=submission.original_filename)
