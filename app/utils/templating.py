"""Jinja2 setup, flash messages and the shared template context."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from app.config import settings
from app.utils.security import CSRF_SESSION_KEY, generate_csrf_token

templates = Jinja2Templates(directory=str(settings.templates_dir))

FLASH_SESSION_KEY = "_flashes"


# --- Flash messages -----------------------------------------------------------


def flash(request: Request, message: str, category: str = "success") -> None:
    """Queue a one-shot message to be shown on the next rendered page.

    `category` maps directly onto a Bootstrap alert modifier
    (success / danger / warning / info).
    """
    request.session.setdefault(FLASH_SESSION_KEY, []).append(
        {"message": message, "category": category}
    )


def pop_flashes(request: Request) -> List[Dict[str, str]]:
    """Read and clear the queued messages."""
    return request.session.pop(FLASH_SESSION_KEY, [])


# --- CSRF ---------------------------------------------------------------------


def get_or_create_csrf_token(request: Request) -> str:
    """Return the session's CSRF token, minting one on first use."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = generate_csrf_token()
        request.session[CSRF_SESSION_KEY] = token
    return token


# --- Rendering ----------------------------------------------------------------


def render(
    request: Request,
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render `template_name` with the shared context merged in.

    Injected for every page:
        app_name, current_year, csrf_token, flashes, current_student, current_teacher
    """
    payload: Dict[str, Any] = {
        "app_name": settings.app_name,
        "current_year": datetime.now(timezone.utc).year,
        "csrf_token": get_or_create_csrf_token(request),
        "flashes": pop_flashes(request),
        # Populated by the `optional_student`/`optional_teacher` dependencies
        # on protected/public pages; defaults to None so the navbar always
        # renders correctly for anonymous visitors.
        "current_student": getattr(request.state, "student", None),
        "current_teacher": getattr(request.state, "teacher", None),
    }
    payload.update(context or {})
    return templates.TemplateResponse(
        request, template_name, payload, status_code=status_code
    )


# --- Filters ------------------------------------------------------------------


def _format_datetime(value: Optional[datetime], fmt: str = "%d %b %Y, %I:%M %p") -> str:
    """Human-friendly timestamp; blank-safe for optional columns."""
    if not value:
        return "—"
    return value.strftime(fmt)


def _format_date(value: Optional[datetime], fmt: str = "%d %B %Y") -> str:
    if not value:
        return "—"
    return value.strftime(fmt)


templates.env.filters["datetime"] = _format_datetime
templates.env.filters["date"] = _format_date
