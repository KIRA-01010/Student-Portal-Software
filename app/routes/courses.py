"""Student course view. Full self-service course discovery can be layered on later."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from starlette.responses import Response
from app.database.session import get_db
from app.models.course import Course, Enrollment
from app.models.student import Student
from app.utils.dependencies import require_student
from app.utils.templating import render

router = APIRouter(tags=["courses"])

@router.get("/courses", name="courses_page")
def courses_page(request: Request, student: Student = Depends(require_student), db: Session = Depends(get_db)) -> Response:
    stmt = select(Course).join(Enrollment, Enrollment.course_id == Course.id).where(Enrollment.student_id == student.id).options(joinedload(Course.teacher)).order_by(Course.name)
    courses = list(db.scalars(stmt).unique().all())
    return render(request, "dashboard/courses.html", {"student": student, "courses": courses})
