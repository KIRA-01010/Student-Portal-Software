"""Student sign-in/sign-out. Student accounts are created by administrators only."""
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.session import get_db
from app.routes import account_flow
from app.routes.account_flow import AccountPortal
from app.schemas.auth import StudentLoginForm
from app.services import auth_service
from app.utils.dependencies import require_guest, verify_csrf

router = APIRouter(tags=["auth"])

STUDENT_PORTAL = AccountPortal(
    service=auth_service,
    register_template="",
    login_template="auth/login.html",
    login_route="login_page",
    home_route="dashboard_page",
    registered_message="",
)


@router.get("/login", name="login_page")
def login_page(request: Request, _: None = Depends(require_guest)) -> Response:
    return account_flow.show_login_page(request, STUDENT_PORTAL)


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    identifier: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_guest),
    __: None = Depends(verify_csrf),
) -> Response:
    form = StudentLoginForm.from_raw(identifier=identifier, password=password)
    return account_flow.submit_login(request, db, STUDENT_PORTAL, form)


@router.post("/logout", name="logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    __: None = Depends(verify_csrf),
) -> Response:
    return account_flow.submit_logout(request, db, STUDENT_PORTAL)
