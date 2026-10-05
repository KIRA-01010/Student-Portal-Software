"""Teacher-only student academic record CRUD, course grades, and record sharing.

Who may do what is decided in `student_record_service` (owner / shared teacher /
administrator); these routes only ask it.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from app.database.session import get_db
from app.models.student_record import StudentRecord
from app.models.teacher import Teacher
from app.schemas.academic import CourseGradeForm, StudentRecordForm
from app.services import cgpa_service, student_record_service
from app.services.exceptions import (
    FieldValidationError,
    RecordLinkError,
    RecordShareError,
)
from app.utils.dependencies import require_teacher, verify_csrf
from app.utils.templating import flash, render

router = APIRouter(prefix="/teacher/students", tags=["teacher-students"])


def _record_or_404(
    db: Session, teacher: Teacher, record_id: int, *, manage: bool = False
) -> StudentRecord:
    """The record, if this teacher may work on it.

    New student records are created by administrators. Teachers can view linked
    records for students on their course rosters and can manage grades, but not
    the student's institutional identity fields.
    """
    record = student_record_service.get_accessible(db, teacher, record_id)
    if record is None:
        raise StarletteHTTPException(status_code=404)
    if manage and not student_record_service.can_manage(teacher, record):
        raise StarletteHTTPException(
            status_code=403,
            detail="Only the record's owner or an administrator can do that.",
        )
    return record


def _record_or_404_for_grades(db: Session, teacher: Teacher, record_id: int) -> StudentRecord:
    """The record, only if this teacher may add/edit/delete its course grades.

    Seeing a record because the student is on this teacher's course roster is
    not enough — that view-only access must not let a teacher rewrite grades
    for courses that aren't theirs. Only the owner, a teacher it was shared
    with, or an administrator may manage grades.
    """
    record = student_record_service.get_accessible(db, teacher, record_id)
    if record is None:
        raise StarletteHTTPException(status_code=404)
    if not student_record_service.can_manage_grades(teacher, record):
        raise StarletteHTTPException(
            status_code=403,
            detail="Only the record's owner, a teacher it's shared with, or an administrator can edit grades.",
        )
    return record


# --- List / search --------------------------------------------------------------


@router.get("", name="teacher_students_list")
def teacher_students_list(
    request: Request,
    q: Optional[str] = None,
    scope: Optional[str] = None,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    # Only administrators may widen the list to every teacher's records.
    show_all = teacher.is_admin and scope == student_record_service.SCOPE_ALL
    records = student_record_service.list_for_teacher(
        db,
        teacher,
        search=q,
        scope=student_record_service.SCOPE_ALL
        if show_all
        else student_record_service.SCOPE_MINE,
    )
    return render(
        request,
        "teacher/students/list.html",
        {
            "records": records,
            "search": q or "",
            "show_all": show_all,
            "cgpa_service": cgpa_service,
            "is_owner": lambda record: student_record_service.is_owner(teacher, record),
            "can_manage": lambda record: student_record_service.can_manage(
                teacher, record
            ),
        },
    )


# --- Create -----------------------------------------------------------------


@router.get("/new", name="teacher_student_new_page")
def teacher_student_new_page(request: Request, teacher: Teacher = Depends(require_teacher)) -> Response:
    raise StarletteHTTPException(status_code=403, detail="Student records are created automatically by administrators.")


@router.post("/new", name="teacher_student_new_submit")
def teacher_student_new_submit(
    request: Request,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    raise StarletteHTTPException(
        status_code=403,
        detail="Student records are created automatically by administrators.",
    )


# --- Detail -------------------------------------------------------------------


@router.get("/{record_id}", name="teacher_student_detail_page")
def teacher_student_detail_page(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    record = _record_or_404(db, teacher, record_id)
    return render(
        request,
        "teacher/students/detail.html",
        {
            "record": record,
            "cgpa": cgpa_service.compute_cgpa(record),
            "semester_breakdown": cgpa_service.semester_breakdown(record),
            "can_manage": student_record_service.can_manage(teacher, record),
            "is_owner": student_record_service.is_owner(teacher, record),
        },
    )


# --- Edit -----------------------------------------------------------------


@router.get("/{record_id}/edit", name="teacher_student_edit_page")
def teacher_student_edit_page(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)
    form = StudentRecordForm(
        registration_number=record.registration_number,
        first_name=record.first_name,
        last_name=record.last_name,
        department=record.department,
        current_semester=str(record.current_semester),
    )
    return render(
        request,
        "teacher/students/form.html",
        {
            "form_values": form.as_form_values(),
            "errors": {},
            "is_edit": True,
            "record": record,
        },
    )


@router.post("/{record_id}/edit", name="teacher_student_edit_submit")
def teacher_student_edit_submit(
    request: Request,
    record_id: int,
    first_name: str = Form(""),
    last_name: str = Form(""),
    department: str = Form(""),
    current_semester: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)

    # Registration number is immutable after creation — it is the record's
    # stable identifier, so it is not accepted from this form.
    form = StudentRecordForm.from_raw(
        registration_number=record.registration_number,
        first_name=first_name,
        last_name=last_name,
        department=department,
        current_semester=current_semester,
    )
    errors = form.validate()
    if errors:
        return render(
            request,
            "teacher/students/form.html",
            {
                "form_values": form.as_form_values(),
                "errors": errors,
                "is_edit": True,
                "record": record,
            },
            status_code=400,
        )

    student_record_service.update_record(
        db,
        record,
        first_name=form.first_name,
        last_name=form.last_name,
        department=form.department,
        current_semester=form.current_semester_int,
    )
    flash(request, "Student record updated.", "success")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


# --- Delete (confirm-before-destroy) ------------------------------------------


@router.get("/{record_id}/delete", name="teacher_student_delete_confirm_page")
def teacher_student_delete_confirm_page(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)
    return render(
        request,
        "teacher/students/delete_confirm.html",
        {"record": record, "cgpa": cgpa_service.compute_cgpa(record)},
    )


@router.post("/{record_id}/delete", name="teacher_student_delete_submit")
def teacher_student_delete_submit(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)
    student_record_service.delete_record(db, record)
    flash(request, "Student record deleted.", "info")
    return RedirectResponse(
        request.url_for("teacher_students_list"), status_code=HTTP_303_SEE_OTHER
    )


# --- Portal access: link a record to a student's account -----------------------


@router.post("/{record_id}/link", name="teacher_student_link_submit")
def teacher_student_link_submit(
    request: Request,
    record_id: int,
    student_login: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    """Let the student with this username/email see this record's grades."""
    record = _record_or_404(db, teacher, record_id, manage=True)
    try:
        student = student_record_service.link_student(db, record, student_login)
    except RecordLinkError as exc:
        flash(request, exc.message, "danger")
    else:
        if student_record_service.names_match(record, student):
            flash(
                request,
                f"Linked to {student.full_name} (Registration No. {student.registration_number}). "
                "They can now see this record under Grades.",
                "success",
            )
        else:
            # Not an error (names can differ), but a typo here would show one
            # student another's grades, so make the mismatch impossible to miss.
            flash(
                request,
                f"Linked to {student.full_name} (Registration No. {student.registration_number}), but that "
                f"name does not match this record ({record.full_name}). "
                "Please double-check it is the right person.",
                "warning",
            )
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


@router.post("/{record_id}/unlink", name="teacher_student_unlink_submit")
def teacher_student_unlink_submit(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)
    student_record_service.unlink_student(db, record)
    flash(request, "The student can no longer see this record.", "info")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


# --- Sharing: which other teachers may work on a record ----------------------------


@router.post("/{record_id}/share", name="teacher_student_share_submit")
def teacher_student_share_submit(
    request: Request,
    record_id: int,
    colleague: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    """Let another approved teacher view and edit this record and its grades."""
    record = _record_or_404(db, teacher, record_id, manage=True)
    try:
        colleague_account = student_record_service.share_with(db, record, colleague)
    except RecordShareError as exc:
        flash(request, exc.message, "danger")
    else:
        flash(
            request,
            f"Shared with {colleague_account.full_name} "
            f"(@{colleague_account.username}). They can now view and edit this record.",
            "success",
        )
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{record_id}/unshare/{teacher_id}", name="teacher_student_unshare_submit"
)
def teacher_student_unshare_submit(
    request: Request,
    record_id: int,
    teacher_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404(db, teacher, record_id, manage=True)
    removed = student_record_service.unshare(db, record, teacher_id)
    if removed is not None:
        flash(request, f"{removed.full_name} can no longer see this record.", "info")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


@router.post("/{record_id}/transfer", name="teacher_student_transfer_submit")
def teacher_student_transfer_submit(
    request: Request,
    record_id: int,
    new_owner: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    """Hand the record to a different owner. Administrators only."""
    record = _record_or_404(db, teacher, record_id)
    if not teacher.is_admin:
        raise StarletteHTTPException(
            status_code=403,
            detail="Only administrators can hand a record to another owner.",
        )
    try:
        owner = student_record_service.transfer_ownership(db, teacher, record, new_owner)
    except RecordShareError as exc:
        flash(request, exc.message, "danger")
    else:
        flash(
            request,
            f"{owner.full_name} (@{owner.username}) now owns this record. "
            "The previous owner no longer has access unless you share it back.",
            "success",
        )
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


# --- Course grades --------------------------------------------------------------


@router.get("/{record_id}/courses/new", name="teacher_course_new_page")
def teacher_course_new_page(
    request: Request,
    record_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    record = _record_or_404_for_grades(db, teacher, record_id)
    return render(
        request,
        "teacher/students/course_form.html",
        {"record": record, "form_values": {}, "errors": {}, "is_edit": False},
    )


@router.post("/{record_id}/courses/new", name="teacher_course_new_submit")
def teacher_course_new_submit(
    request: Request,
    record_id: int,
    semester: str = Form(""),
    course_name: str = Form(""),
    credit_hours: str = Form(""),
    grade: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404_for_grades(db, teacher, record_id)
    form = CourseGradeForm.from_raw(
        semester=semester,
        course_name=course_name,
        credit_hours=credit_hours,
        grade=grade,
    )
    errors = form.validate()
    if errors:
        return render(
            request,
            "teacher/students/course_form.html",
            {
                "record": record,
                "form_values": form.as_form_values(),
                "errors": errors,
                "is_edit": False,
            },
            status_code=400,
        )

    student_record_service.add_course_grade(
        db,
        record,
        semester=form.semester_int,
        course_name=form.course_name,
        credit_hours=form.credit_hours_int,
        grade=form.grade,
    )
    flash(request, "Course grade added. CGPA updated.", "success")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{record_id}/courses/{course_id}/edit", name="teacher_course_edit_page"
)
def teacher_course_edit_page(
    request: Request,
    record_id: int,
    course_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    record = _record_or_404_for_grades(db, teacher, record_id)
    course_grade = student_record_service.get_course_grade(db, record, course_id)
    if course_grade is None:
        raise StarletteHTTPException(status_code=404)

    form = CourseGradeForm(
        semester=str(course_grade.semester),
        course_name=course_grade.course_name,
        credit_hours=str(course_grade.credit_hours),
        grade=course_grade.grade,
    )
    return render(
        request,
        "teacher/students/course_form.html",
        {
            "record": record,
            "course_grade": course_grade,
            "form_values": form.as_form_values(),
            "errors": {},
            "is_edit": True,
        },
    )


@router.post(
    "/{record_id}/courses/{course_id}/edit", name="teacher_course_edit_submit"
)
def teacher_course_edit_submit(
    request: Request,
    record_id: int,
    course_id: int,
    semester: str = Form(""),
    course_name: str = Form(""),
    credit_hours: str = Form(""),
    grade: str = Form(""),
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404_for_grades(db, teacher, record_id)
    course_grade = student_record_service.get_course_grade(db, record, course_id)
    if course_grade is None:
        raise StarletteHTTPException(status_code=404)

    form = CourseGradeForm.from_raw(
        semester=semester,
        course_name=course_name,
        credit_hours=credit_hours,
        grade=grade,
    )
    errors = form.validate()
    if errors:
        return render(
            request,
            "teacher/students/course_form.html",
            {
                "record": record,
                "course_grade": course_grade,
                "form_values": form.as_form_values(),
                "errors": errors,
                "is_edit": True,
            },
            status_code=400,
        )

    student_record_service.update_course_grade(
        db,
        course_grade,
        semester=form.semester_int,
        course_name=form.course_name,
        credit_hours=form.credit_hours_int,
        grade=form.grade,
    )
    flash(request, "Course grade updated. CGPA updated.", "success")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{record_id}/courses/{course_id}/delete", name="teacher_course_delete_submit"
)
def teacher_course_delete_submit(
    request: Request,
    record_id: int,
    course_id: int,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    record = _record_or_404_for_grades(db, teacher, record_id)
    course_grade = student_record_service.get_course_grade(db, record, course_id)
    if course_grade is None:
        raise StarletteHTTPException(status_code=404)

    student_record_service.delete_course_grade(db, course_grade)
    flash(request, "Course grade removed. CGPA updated.", "info")
    return RedirectResponse(
        request.url_for("teacher_student_detail_page", record_id=record.id),
        status_code=HTTP_303_SEE_OTHER,
    )
