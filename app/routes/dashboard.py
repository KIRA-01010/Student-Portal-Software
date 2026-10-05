"""Protected student area: dashboard, grades and profile placeholder."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.session import get_db
from app.models.student import Student
from app.services import auth_service, cgpa_service, student_record_service
from app.utils.dependencies import require_student
from app.utils.templating import render

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", name="dashboard_page")
def dashboard_page(
    request: Request,
    student: Student = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    record = student_record_service.get_for_student(db, student.id)
    return render(
        request,
        "dashboard/index.html",
        {
            "student": student,
            # The timestamp of the login *before* this one, so the card shows
            # something meaningful instead of "a second ago".
            "previous_login": auth_service.get_previous_login(request),
            # The academic record a teacher linked to this account, if any.
            "record": record,
            "cgpa": cgpa_service.compute_cgpa(record) if record else None,
        },
    )


@router.get("/grades", name="grades_page")
def grades_page(
    request: Request,
    student: Student = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    """The signed-in student's own results, read-only.

    The record is found from the *session's* student id, never from anything in
    the URL or form, so there is no way to ask for someone else's grades.
    """
    record = student_record_service.get_for_student(db, student.id)
    return render(
        request,
        "dashboard/grades.html",
        {
            "student": student,
            "record": record,
            "cgpa": cgpa_service.compute_cgpa(record) if record else None,
            "semester_breakdown": (
                cgpa_service.semester_breakdown(record) if record else []
            ),
        },
    )


@router.get("/profile", name="profile_page")
def profile_page(
    request: Request, student: Student = Depends(require_student)
) -> Response:
    """Placeholder — Phase 2 will make these fields editable."""
    return render(request, "dashboard/profile.html", {"student": student})
