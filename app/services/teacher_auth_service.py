"""Teacher authentication — the shared account logic bound to `Teacher`.

See `account_auth` for the behaviour. Teachers and students get separate
throttling scopes and session roles, so one can never be mistaken for the other.
Unlike students, teachers must also be approved by an administrator.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.teacher import Teacher, TeacherStatus
from app.schemas.teacher_auth import TeacherLoginForm, TeacherRegistrationForm
from app.services import account_auth, teacher_service
from app.services.account_auth import AccountKind
from app.services.exceptions import AccountNotApprovedError


def _require_approved(teacher: Teacher) -> None:
    """Only approved teachers may sign in or keep a session."""
    if teacher.status != TeacherStatus.APPROVED:
        raise AccountNotApprovedError(teacher.status)


TEACHER = AccountKind(
    role="teacher",
    repository=teacher_service.repository,
    access_check=_require_approved,
)


def register_teacher(db: Session, form: TeacherRegistrationForm) -> Teacher:
    """Create a teacher account. It stays ``pending`` until an admin approves it."""
    return account_auth.register(
        db,
        TEACHER,
        form,
        department=form.department or None,
        status=TeacherStatus.PENDING,
    )


def register(db: Session, form: TeacherRegistrationForm):
    """Uniform name for the shared route flow (see `routes.account_flow`)."""
    return register_teacher(db, form)


def authenticate(db: Session, form: TeacherLoginForm, *, client_ip: str) -> Teacher:
    return account_auth.authenticate(db, TEACHER, form, client_ip=client_ip)


def login_session(request: Request, db: Session, teacher: Teacher) -> None:
    account_auth.start_login(request, db, TEACHER, teacher)


def logout_session(request: Request, db: Session) -> None:
    account_auth.end_login(request, db)


def get_current_teacher(request: Request, db: Session) -> Optional[Teacher]:
    return account_auth.current_account(request, db, TEACHER)


def get_previous_login(request: Request) -> Optional[datetime]:
    return account_auth.get_previous_login(request)
