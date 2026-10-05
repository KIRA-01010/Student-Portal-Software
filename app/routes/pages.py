"""Public, non-authenticated pages."""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_302_FOUND

from app.models.student import Student
from app.utils.dependencies import optional_student

router = APIRouter(tags=["pages"])


@router.get("/", name="home", include_in_schema=False)
def home(
    request: Request, student: Optional[Student] = Depends(optional_student)
) -> Response:
    """Send visitors to the right place depending on their session."""
    target = "dashboard_page" if student else "login_page"
    return RedirectResponse(request.url_for(target), status_code=HTTP_302_FOUND)


@router.get("/healthz", name="healthz", include_in_schema=False)
def healthz() -> dict:
    """Liveness probe for local tooling / container orchestrators."""
    return {"status": "ok"}
