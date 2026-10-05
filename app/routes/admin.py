"""Administrator-only management pages for teachers, students and the course catalog."""
from datetime import datetime, timezone
import re
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from app.database.session import get_db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.course import Course
from app.services import course_service, student_service, teacher_admin_service
from app.services.exceptions import AdminActionError
from app.utils.dependencies import require_admin, verify_csrf
from app.utils.templating import flash, render
from app.utils.security import MAX_PASSWORD_BYTES
from app.utils import validators as v

router = APIRouter(prefix="/admin", tags=["admin"])
SEASONS = ("Fall", "Spring")
ENTRY_TYPES = ("Regular", "Lateral")
SEMESTERS = tuple(range(1, 9))


def _teacher_or_404(db: Session, teacher_id: int) -> Teacher:
    teacher = teacher_admin_service.get_teacher(db, teacher_id)
    if teacher is None:
        raise StarletteHTTPException(status_code=404)
    return teacher


def _student_form_context(db: Session, *, form_values=None, errors=None, form_error=None, filters=None):
    filters = filters or {}
    stmt = select(Student)
    if filters.get("season") in SEASONS:
        stmt = stmt.where(Student.season == filters["season"])
    if filters.get("academic_year"):
        stmt = stmt.where(Student.academic_year == int(filters["academic_year"]))
    if filters.get("semester"):
        stmt = stmt.where(Student.current_semester == int(filters["semester"]))
    if filters.get("department"):
        stmt = stmt.where(Student.department == filters["department"])
    stmt = stmt.order_by(Student.season, Student.academic_year.desc(), Student.current_semester, Student.department, Student.last_name, Student.first_name)
    students = list(db.scalars(stmt).all())
    departments = list(db.scalars(select(Student.department).where(Student.department.is_not(None)).distinct().order_by(Student.department)).all())
    years = list(db.scalars(select(Student.academic_year).where(Student.academic_year.is_not(None)).distinct().order_by(Student.academic_year.desc())).all())
    return {
        "students": students, "seasons": SEASONS, "entry_types": ENTRY_TYPES, "semesters": SEMESTERS,
        "departments": departments, "years": years, "current_year": datetime.now(timezone.utc).year,
        "form_values": form_values or {}, "errors": errors or {}, "form_error": form_error, "filters": filters,
    }


@router.get("/teachers", name="admin_teachers_page")
def admin_teachers_page(request: Request, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    return render(request, "admin/teachers.html", {"pending": teacher_admin_service.list_pending(db), "reviewed": teacher_admin_service.list_reviewed(db)})


@router.post("/teachers/{teacher_id}/approve", name="admin_teacher_approve")
def admin_teacher_approve(request: Request, teacher_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    teacher = _teacher_or_404(db, teacher_id)
    try:
        teacher_admin_service.approve(db, admin, teacher)
    except AdminActionError as exc:
        flash(request, exc.message, "danger")
    else:
        flash(request, f"{teacher.full_name} can now sign in.", "success")
    return RedirectResponse(request.url_for("admin_teachers_page"), status_code=HTTP_303_SEE_OTHER)


@router.post("/teachers/{teacher_id}/reject", name="admin_teacher_reject")
def admin_teacher_reject(request: Request, teacher_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    teacher = _teacher_or_404(db, teacher_id)
    try:
        teacher_admin_service.reject(db, admin, teacher)
    except AdminActionError as exc:
        flash(request, exc.message, "danger")
    else:
        flash(request, f"{teacher.full_name} can no longer sign in.", "info")
    return RedirectResponse(request.url_for("admin_teachers_page"), status_code=HTTP_303_SEE_OTHER)


@router.get("/students", name="admin_students_page")
def admin_students_page(request: Request, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), season: Optional[str] = None, academic_year: Optional[int] = None, semester: Optional[int] = None, department: Optional[str] = None) -> Response:
    filters = {"season": season or "", "academic_year": academic_year or "", "semester": semester or "", "department": department or ""}
    return render(request, "admin/students.html", _student_form_context(db, filters=filters))


def _validate_student_form(registration_number, first_name, last_name, email, password, confirm_password, department, season, academic_year, semester, entry_type, db, existing_student=None):
    values = {"registration_number": registration_number.strip(), "first_name": first_name.strip(), "last_name": last_name.strip(), "email": email.strip().lower(), "department": department.strip(), "season": season, "academic_year": academic_year.strip(), "current_semester": semester.strip(), "entry_type": entry_type}
    errors = {}
    if not re.fullmatch(r"\d{8}", values["registration_number"]):
        errors["registration_number"] = "Registration number must be exactly 8 digits."
    elif existing_student is None and student_service.registration_number_exists(db, values["registration_number"]):
        errors["registration_number"] = "Registration number is already assigned to another student."
    if err := v.validate_name(values["first_name"], "First name"): errors["first_name"] = err
    if err := v.validate_name(values["last_name"], "Last name"): errors["last_name"] = err
    if err := v.validate_email_address(values["email"]): errors["email"] = err
    elif student_service.email_exists(db, values["email"]) and (existing_student is None or existing_student.email != values["email"]): errors["email"] = "Email already exists."
    if err := v.validate_department(values["department"]): errors["department"] = err
    if values["season"] not in SEASONS: errors["season"] = "Select Fall or Spring."
    try:
        year = int(values["academic_year"])
        if year < 2000 or year > 2100: raise ValueError
    except ValueError:
        errors["academic_year"] = "Enter a valid academic year."; year = datetime.now(timezone.utc).year
    try:
        sem = int(values["current_semester"])
        if sem not in SEMESTERS: raise ValueError
    except ValueError:
        errors["current_semester"] = "Semester must be between 1 and 8."; sem = 1
    if values["entry_type"] not in ENTRY_TYPES: errors["entry_type"] = "Select Regular or Lateral."
    if existing_student is None:
        if err := v.validate_password(password): errors["password"] = err
        elif password != confirm_password: errors["confirm_password"] = "Passwords do not match."
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES: errors["password"] = f"Password is too long (maximum {MAX_PASSWORD_BYTES} bytes)."
    return values, errors, year, sem


@router.post("/students", name="admin_student_create")
def admin_student_create(request: Request, registration_number: str = Form(""), first_name: str = Form(""), last_name: str = Form(""), email: str = Form(""), password: str = Form(""), confirm_password: str = Form(""), department: str = Form(""), season: str = Form(""), academic_year: str = Form(""), current_semester: str = Form(""), entry_type: str = Form(""), admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    values, errors, year, sem = _validate_student_form(registration_number, first_name, last_name, email, password, confirm_password, department, season, academic_year, current_semester, entry_type, db)
    if errors:
        ctx = _student_form_context(db, form_values={**values, "academic_year": values["academic_year"], "current_semester": values["current_semester"]}, errors=errors, form_error="Please correct the highlighted fields.")
        return render(request, "admin/students.html", ctx, status_code=400)
    try:
        student = student_service.create_admin_student(db, registration_number=values["registration_number"], first_name=values["first_name"], last_name=values["last_name"], email=values["email"], password=password, department=values["department"], season=values["season"], academic_year=year, current_semester=sem, entry_type=values["entry_type"], created_by_teacher_id=admin.id)
    except (IntegrityError, ValueError) as exc:
        flash(request, str(exc) or "That registration number or email is already in use.", "danger")
    else:
        enrolled = course_service.enroll_student_in_matching_courses(db, student)
        message = f"Student {values['registration_number']} and their academic record were created successfully."
        if enrolled:
            message += f" Automatically enrolled in {enrolled} course{'s' if enrolled != 1 else ''} for their {values['season']} {year} · Semester {sem} · {values['department']} offering."
        flash(request, message, "success")
    return RedirectResponse(request.url_for("admin_students_page"), status_code=HTTP_303_SEE_OTHER)


@router.get("/students/{student_id}/edit", name="admin_student_edit_page")
def admin_student_edit_page(request: Request, student_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    student = db.get(Student, student_id)
    if student is None: raise StarletteHTTPException(status_code=404)
    values = {"registration_number": student.registration_number, "first_name": student.first_name, "last_name": student.last_name, "email": student.email, "department": student.department, "season": student.season, "academic_year": str(student.academic_year), "current_semester": str(student.current_semester), "entry_type": student.entry_type}
    return render(request, "admin/student_edit.html", {"student": student, "form_values": values, "errors": {}, "seasons": SEASONS, "entry_types": ENTRY_TYPES, "semesters": SEMESTERS, "current_year": datetime.now(timezone.utc).year})


@router.post("/students/{student_id}/edit", name="admin_student_edit_submit")
def admin_student_edit_submit(request: Request, student_id: int, first_name: str = Form(""), last_name: str = Form(""), email: str = Form(""), department: str = Form(""), season: str = Form(""), academic_year: str = Form(""), current_semester: str = Form(""), entry_type: str = Form(""), admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    student = db.get(Student, student_id)
    if student is None: raise StarletteHTTPException(status_code=404)
    values = {"registration_number": student.registration_number, "first_name": first_name.strip(), "last_name": last_name.strip(), "email": email.strip().lower(), "department": department.strip(), "season": season, "academic_year": academic_year.strip(), "current_semester": current_semester.strip(), "entry_type": entry_type}
    _, errors, year, sem = _validate_student_form(student.registration_number, first_name, last_name, email, "", "", department, season, academic_year, current_semester, entry_type, db, existing_student=student)
    if errors:
        return render(request, "admin/student_edit.html", {"student": student, "form_values": values, "errors": errors, "seasons": SEASONS, "entry_types": ENTRY_TYPES, "semesters": SEMESTERS, "current_year": datetime.now(timezone.utc).year, "form_error": "Please correct the highlighted fields."}, status_code=400)
    student.first_name, student.last_name, student.email = values["first_name"], values["last_name"], values["email"]
    student.department, student.season, student.academic_year = values["department"], values["season"], year
    student.current_semester, student.entry_type = sem, values["entry_type"]
    if student.academic_record is not None:
        student.academic_record.first_name = student.first_name
        student.academic_record.last_name = student.last_name
        student.academic_record.department = student.department
        student.academic_record.current_semester = student.current_semester
        student.academic_record.registration_number = student.registration_number
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "That email is already in use.", "danger")
    else:
        # If the offering (season/year/semester/department) changed, pick up
        # any courses the student wasn't already enrolled in. Existing
        # enrollments in courses that no longer match are left as-is — a
        # teacher can remove them by hand from the course roster.
        course_service.enroll_student_in_matching_courses(db, student)
        flash(request, f"Student {student.registration_number} was updated successfully.", "success")
    return RedirectResponse(request.url_for("admin_students_page"), status_code=HTTP_303_SEE_OTHER)


def _parse_category(season: Optional[str], academic_year: Optional[str], semester: Optional[str], department: Optional[str]) -> Optional[dict]:
    """The category (season/year/semester/department) if all four are present and valid, else None.

    A category is not a separate row in the database — it is just the
    combination of fields every course and student already carries. Picking
    one here is how the admin says "courses I add next belong to this
    offering", so they land on it without retyping it each time.
    """
    if not (season and academic_year and semester and department):
        return None
    if season not in SEASONS:
        return None
    try:
        year = int(academic_year)
        if year < 2000 or year > 2100:
            return None
    except (TypeError, ValueError):
        return None
    try:
        sem = int(semester)
        if sem not in SEMESTERS:
            return None
    except (TypeError, ValueError):
        return None
    department = department.strip()
    if v.validate_department(department):
        return None
    return {"season": season, "academic_year": year, "semester": sem, "department": department}


def _courses_page_context(db: Session, *, category=None, form_values=None, errors=None, form_error=None):
    stmt = select(Course).options(joinedload(Course.teacher), joinedload(Course.enrollments), joinedload(Course.assignments))
    if category:
        stmt = stmt.where(Course.season == category["season"], Course.academic_year == category["academic_year"], Course.semester == category["semester"], Course.department == category["department"])
    stmt = stmt.order_by(Course.archived, Course.academic_year.desc(), Course.semester, Course.name)
    courses = list(db.scalars(stmt).unique().all())
    return {
        "courses": courses, "seasons": SEASONS, "entry_types": ENTRY_TYPES, "semesters": SEMESTERS,
        "current_year": datetime.now(timezone.utc).year, "category": category,
        "form_values": form_values or {}, "errors": errors or {}, "form_error": form_error,
    }


@router.get("/courses", name="admin_courses_page")
def admin_courses_page(request: Request, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), season: Optional[str] = None, academic_year: Optional[str] = None, semester: Optional[str] = None, department: Optional[str] = None) -> Response:
    category = _parse_category(season, academic_year, semester, department)
    return render(request, "admin/courses.html", _courses_page_context(db, category=category))


@router.post("/courses", name="admin_course_create")
def admin_course_create(request: Request, name: str = Form(""), code: str = Form(""), description: str = Form(""), season: str = Form(""), academic_year: str = Form(""), semester: str = Form(""), department: str = Form(""), entry_type: str = Form(""), admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    values = {"name": name.strip(), "code": code.strip().upper(), "description": description.strip(), "season": season, "academic_year": academic_year.strip(), "semester": semester.strip(), "department": department.strip(), "entry_type": entry_type}
    # The category (season/year/semester/department) was already chosen on the
    # previous page; re-validate it here too since it travels through hidden
    # form fields a client could tamper with.
    category = _parse_category(season, academic_year.strip(), semester.strip(), department.strip())
    errors = {}
    if not values["name"]: errors["name"] = "Course name is required."
    if not values["code"]: errors["code"] = "Course code is required."
    if category is None:
        errors["category"] = "Choose a valid season, year, semester and department first."
    if values["entry_type"] not in ENTRY_TYPES: errors["entry_type"] = "Select Regular or Lateral."
    if errors:
        ctx = _courses_page_context(db, category=category, form_values=values, errors=errors, form_error="Please correct the highlighted fields.")
        return render(request, "admin/courses.html", ctx, status_code=400)
    try:
        course = course_service.create_course(db, name=values["name"], code=values["code"], description=values["description"], season=category["season"], academic_year=category["academic_year"], semester=category["semester"], department=category["department"], entry_type=values["entry_type"])
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        enrolled = course_service.enroll_matching_students(db, course)
        message = f"{course.code} added to the catalog. A teacher can now claim it."
        if enrolled:
            message += f" {enrolled} student{'s' if enrolled != 1 else ''} already in this offering were enrolled automatically."
        flash(request, message, "success")
    query = urlencode({"season": category["season"], "academic_year": category["academic_year"], "semester": category["semester"], "department": category["department"]})
    return RedirectResponse(f"{request.url_for('admin_courses_page')}?{query}", status_code=HTTP_303_SEE_OTHER)


@router.post("/courses/{course_id}/delete", name="admin_course_delete")
def admin_course_delete(request: Request, course_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    course = course_service.get_course(db, course_id)
    if course is None: raise StarletteHTTPException(status_code=404)
    students, assignments = course_service.course_counts(db, course_id)
    if students or assignments:
        flash(request, "This course has student enrollments or assignments, so it cannot be permanently deleted. Use Archive instead.", "warning")
    elif course_service.delete_course(db, course_id):
        flash(request, f"{course.code} was permanently deleted.", "info")
    return RedirectResponse(request.url_for("admin_courses_page"), status_code=HTTP_303_SEE_OTHER)


@router.post("/courses/{course_id}/archive", name="admin_course_archive")
def admin_course_archive(request: Request, course_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    course = course_service.archive_course(db, course_id)
    if course is None: raise StarletteHTTPException(status_code=404)
    flash(request, f"{course.code} was archived. Its students, assignments and submissions were preserved.", "info")
    return RedirectResponse(request.url_for("admin_courses_page"), status_code=HTTP_303_SEE_OTHER)


@router.post("/courses/{course_id}/restore", name="admin_course_restore")
def admin_course_restore(request: Request, course_id: int, admin: Teacher = Depends(require_admin), db: Session = Depends(get_db), __: None = Depends(verify_csrf)) -> Response:
    course = course_service.restore_course(db, course_id)
    if course is None: raise StarletteHTTPException(status_code=404)
    flash(request, f"{course.code} is active again and can be claimed when it is unassigned.", "success")
    return RedirectResponse(request.url_for("admin_courses_page"), status_code=HTTP_303_SEE_OTHER)
