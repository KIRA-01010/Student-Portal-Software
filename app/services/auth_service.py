"""Student authentication — the shared account logic bound to `Student`.

See `account_auth` for the behaviour; this module only supplies the role and
repository so the routes can keep calling student-named functions.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.student import Student
from app.schemas.auth import LoginForm, RegistrationForm
from app.services import account_auth, student_service
from app.services.account_auth import AccountKind

STUDENT = AccountKind(role="student", repository=student_service.repository)


def register_student(db: Session, form: RegistrationForm) -> Student:
    return account_auth.register(db, STUDENT, form)


def register(db: Session, form: RegistrationForm):
    """Uniform name for the shared route flow (see `routes.account_flow`)."""
    return register_student(db, form)


def authenticate(db: Session, form: LoginForm, *, client_ip: str) -> Student:
    return account_auth.authenticate(db, STUDENT, form, client_ip=client_ip)


def login_session(request: Request, db: Session, student: Student) -> None:
    account_auth.start_login(request, db, STUDENT, student)


def logout_session(request: Request, db: Session) -> None:
    account_auth.end_login(request, db)


def get_current_student(request: Request, db: Session) -> Optional[Student]:
    return account_auth.current_account(request, db, STUDENT)


def get_previous_login(request: Request) -> Optional[datetime]:
    return account_auth.get_previous_login(request)
