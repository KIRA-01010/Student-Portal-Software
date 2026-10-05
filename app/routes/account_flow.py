"""The register / sign-in / sign-out page flow, written once for every account type.

Student and teacher routes used to be near-copies: same validation, same error
statuses (400 / 401 / 403 / 429), same redirects, same lockout header. That
meant every change to the sign-in flow had to be made twice. Now the flow lives
here, and each router only declares what is genuinely its own — its URL, its
form fields, its guard dependencies and an `AccountPortal` naming the pages and
service to use.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from app.services.exceptions import (
    AccountNotApprovedError,
    FieldValidationError,
    InvalidCredentialsError,
    LoginThrottledError,
)
from app.utils.network import client_ip
from app.utils.templating import flash, render


@dataclass(frozen=True)
class AccountPortal:
    """What differs between the student and the teacher sign-in pages."""

    # A module exposing register / authenticate / login_session / logout_session
    # (`auth_service` for students, `teacher_auth_service` for teachers). It is
    # looked up when a request arrives, not when this object is built.
    service: Any
    register_template: str
    login_template: str
    login_route: str  # route name of the sign-in page
    home_route: str  # route name of where a successful sign-in lands
    registered_message: str
    registered_category: str = "success"


def show_register_page(request: Request, portal: AccountPortal) -> Response:
    return render(request, portal.register_template, {"form_values": {}, "errors": {}})


def show_login_page(request: Request, portal: AccountPortal) -> Response:
    return render(request, portal.login_template, {"form_values": {}, "errors": {}})


def submit_register(
    request: Request, db: Session, portal: AccountPortal, form: Any
) -> Response:
    try:
        portal.service.register(db, form)
    except FieldValidationError as exc:
        # Re-render with inline errors and the (non-secret) values preserved.
        return render(
            request,
            portal.register_template,
            {
                "form_values": form.as_form_values(),
                "errors": exc.errors,
                "form_error": exc.message,
            },
            status_code=400,
        )

    flash(request, portal.registered_message, portal.registered_category)
    return RedirectResponse(
        request.url_for(portal.login_route), status_code=HTTP_303_SEE_OTHER
    )


def _login_failed(
    request: Request,
    portal: AccountPortal,
    form: Any,
    message: str,
    status_code: int,
    **extra: Any,
) -> Response:
    return render(
        request,
        portal.login_template,
        {
            "form_values": form.as_form_values(),
            "errors": {},
            "form_error": message,
            **extra,
        },
        status_code=status_code,
    )


def submit_login(
    request: Request, db: Session, portal: AccountPortal, form: Any
) -> Response:
    errors = form.validate()
    if errors:
        return render(
            request,
            portal.login_template,
            {
                "form_values": form.as_form_values(),
                "errors": errors,
                "form_error": "Please fill in both fields.",
            },
            status_code=400,
        )

    try:
        account = portal.service.authenticate(db, form, client_ip=client_ip(request))
    except LoginThrottledError as exc:
        response = _login_failed(request, portal, form, exc.message, 429)
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response
    except AccountNotApprovedError as exc:
        # Correct password, but not allowed in yet: say so, without a session.
        return _login_failed(
            request, portal, form, exc.message, 403, form_error_kind="warning"
        )
    except InvalidCredentialsError as exc:
        return _login_failed(request, portal, form, exc.message, 401)

    portal.service.login_session(request, db, account)
    flash(request, f"Welcome back, {account.first_name}!", "success")
    return RedirectResponse(
        request.url_for(portal.home_route), status_code=HTTP_303_SEE_OTHER
    )


def submit_logout(request: Request, db: Session, portal: AccountPortal) -> Response:
    portal.service.logout_session(request, db)
    flash(request, "You have been signed out.", "info")
    return RedirectResponse(
        request.url_for(portal.login_route), status_code=HTTP_303_SEE_OTHER
    )
