"""Teacher authentication routes: register, login, logout.

Same page flow as the student routes (see `account_flow`). What is different
here: the URLs, the department field on the registration form, and that a new
teacher account waits for administrator approval before it can sign in.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.session import get_db
from app.routes import account_flow
from app.routes.account_flow import AccountPortal
from app.schemas.teacher_auth import TeacherLoginForm, TeacherRegistrationForm
from app.services import teacher_auth_service
from app.utils.dependencies import require_teacher_guest, verify_csrf

router = APIRouter(prefix="/teacher", tags=["teacher-auth"])

TEACHER_PORTAL = AccountPortal(
    service=teacher_auth_service,
    register_template="teacher/register.html",
    login_template="teacher/login.html",
    login_route="teacher_login_page",
    home_route="teacher_dashboard_page",
    registered_message=(
        "Registration received. An administrator needs to approve your account "
        "before you can sign in."
    ),
    registered_category="info",
)


# --- Registration -------------------------------------------------------------


@router.get("/register", name="teacher_register_page")
def teacher_register_page(
    request: Request, _: None = Depends(require_teacher_guest)
) -> Response:
    return account_flow.show_register_page(request, TEACHER_PORTAL)


@router.post("/register", name="teacher_register_submit")
def teacher_register_submit(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    username: str = Form(""),
    department: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_teacher_guest),
    __: None = Depends(verify_csrf),
) -> Response:
    form = TeacherRegistrationForm.from_raw(
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=username,
        department=department,
        password=password,
        confirm_password=confirm_password,
    )
    return account_flow.submit_register(request, db, TEACHER_PORTAL, form)


# --- Login --------------------------------------------------------------------


@router.get("/login", name="teacher_login_page")
def teacher_login_page(
    request: Request, _: None = Depends(require_teacher_guest)
) -> Response:
    return account_flow.show_login_page(request, TEACHER_PORTAL)


@router.post("/login", name="teacher_login_submit")
def teacher_login_submit(
    request: Request,
    identifier: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_teacher_guest),
    __: None = Depends(verify_csrf),
) -> Response:
    form = TeacherLoginForm.from_raw(identifier=identifier, password=password)
    return account_flow.submit_login(request, db, TEACHER_PORTAL, form)


# --- Logout -------------------------------------------------------------------


@router.post("/logout", name="teacher_logout")
def teacher_logout(
    request: Request,
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    return account_flow.submit_logout(request, db, TEACHER_PORTAL)
