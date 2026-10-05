"""FastAPI dependencies for session-based auth and CSRF enforcement."""

from typing import Optional

from fastapi import Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database.session import get_db
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import auth_service, teacher_auth_service
from app.utils.exceptions import CsrfError, NotAuthenticatedError
from app.utils.security import CSRF_FIELD_NAME, CSRF_SESSION_KEY, csrf_token_is_valid


def optional_student(
    request: Request, db: Session = Depends(get_db)
) -> Optional[Student]:
    """Resolve the logged-in student if there is one; never blocks the request.

    The result is cached on `request.state` so templates (navbar, footer) can
    read it without another query.
    """
    student = auth_service.get_current_student(request, db)
    request.state.student = student
    return student


def require_student(
    student: Optional[Student] = Depends(optional_student),
) -> Student:
    """Guard protected routes — redirects anonymous visitors to the login page."""
    if student is None:
        raise NotAuthenticatedError()
    return student


def require_guest(student: Optional[Student] = Depends(optional_student)) -> None:
    """Keep already-authenticated students off the login/register pages."""
    if student is not None:
        raise NotAuthenticatedError(redirect_to="/dashboard", authenticated=True)


async def verify_csrf(
    request: Request,
    csrf_token: str = Form("", alias=CSRF_FIELD_NAME),
) -> None:
    """Reject form posts that do not carry the session's CSRF token."""
    if not csrf_token_is_valid(request.session.get(CSRF_SESSION_KEY, ""), csrf_token):
        raise CsrfError()


def optional_teacher(
    request: Request, db: Session = Depends(get_db)
) -> Optional[Teacher]:
    """Resolve the logged-in teacher if there is one; never blocks the request.

    Uses a session key (`teacher_id`) distinct from the student session key,
    so a student session never resolves a teacher and vice versa.
    """
    teacher = teacher_auth_service.get_current_teacher(request, db)
    request.state.teacher = teacher
    return teacher


def require_teacher(
    teacher: Optional[Teacher] = Depends(optional_teacher),
) -> Teacher:
    """Guard teacher-only routes — redirects anonymous visitors to teacher login."""
    if teacher is None:
        raise NotAuthenticatedError(redirect_to="/teacher/login")
    return teacher


def require_teacher_guest(teacher: Optional[Teacher] = Depends(optional_teacher)) -> None:
    """Keep already-authenticated teachers off the teacher login/register pages."""
    if teacher is not None:
        raise NotAuthenticatedError(
            redirect_to="/teacher/dashboard", authenticated=True
        )


def require_admin(teacher: Teacher = Depends(require_teacher)) -> Teacher:
    """Guard admin-only routes.

    Anonymous visitors are sent to the teacher login (via `require_teacher`);
    a signed-in teacher who is not an administrator gets a 403 page. The flag is
    read from the database on every request, so removing it takes effect at once.
    """
    if not teacher.is_admin:
        raise StarletteHTTPException(
            status_code=403, detail="You don't have permission to view that page."
        )
    return teacher
