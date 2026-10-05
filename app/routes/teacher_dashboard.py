"""Teacher dashboard: stats overview."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.session import get_db
from app.models.teacher import Teacher
from app.services import course_service
from app.services import (
    cgpa_service,
    student_record_service,
    teacher_admin_service,
    teacher_auth_service,
)
from app.utils.dependencies import require_teacher
from app.utils.templating import render

router = APIRouter(prefix="/teacher", tags=["teacher-dashboard"])


@router.get("/dashboard", name="teacher_dashboard_page")
def teacher_dashboard_page(
    request: Request,
    teacher: Teacher = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    records = student_record_service.list_for_teacher(db, teacher)
    course_students = set()
    for course in course_service.courses_for_teacher(db, teacher.id):
        course_students.update(e.student_id for e in course.enrollments)
    recent_records = records[:5]
    return render(
        request,
        "teacher/dashboard.html",
        {
            "teacher": teacher,
            "total_students": len(course_students),
            "recent_records": recent_records,
            "cgpa_service": cgpa_service,
            "previous_login": teacher_auth_service.get_previous_login(request),
            # Only admins are told about sign-ups waiting for them.
            "pending_teachers": (
                teacher_admin_service.pending_count(db) if teacher.is_admin else 0
            ),
        },
    )
