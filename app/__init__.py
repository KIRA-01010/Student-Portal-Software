"""Application factory.

Wiring order matters: session middleware first (everything below it needs
`request.session`), then routes, then the error handlers that turn domain
exceptions into friendly pages.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from app.config import settings
from app.routes import api_router
from app.utils.exceptions import CsrfError, NotAuthenticatedError
from app.utils.templating import flash, render

logger = logging.getLogger("student_portal")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Student Portal — authentication and dashboard (Phase 1).",
        version="1.0.0",
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    # --- Middleware ----------------------------------------------------------
    # Signed, HttpOnly cookie session. `same_site=lax` blocks the cookie on
    # cross-site POSTs, which is a second layer of CSRF defence.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.session_https_only,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:;",
        )
        if request.url.scheme == "https" or settings.session_https_only:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    # --- Static files & routes ----------------------------------------------
    app.mount(
        "/static",
        StaticFiles(directory=str(settings.static_dir)),
        name="static",
    )
    app.include_router(api_router)

    _register_exception_handlers(app)

    logger.info("%s application created (debug=%s)", settings.app_name, settings.debug)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Translate exceptions into redirects or friendly error pages."""

    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(
        request: Request, exc: NotAuthenticatedError
    ) -> Response:
        if not exc.authenticated:
            flash(request, "Please sign in to access that page.", "warning")
        return RedirectResponse(exc.redirect_to, status_code=HTTP_303_SEE_OTHER)

    @app.exception_handler(CsrfError)
    async def _csrf_failed(request: Request, exc: CsrfError) -> Response:
        flash(request, exc.message, "danger")
        # Bounce back to the page the form was posted from. Redirecting to the
        # POST url itself would 404 on POST-only routes such as /logout, and an
        # off-site Referer must never be used as a redirect target.
        referer = request.headers.get("referer", "")
        base_url = str(request.base_url)
        target = referer if referer.startswith(base_url) else "/"
        return RedirectResponse(target, status_code=HTTP_303_SEE_OTHER)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> Response:
        if exc.status_code == 404:
            return render(request, "errors/404.html", status_code=404)
        return render(
            request,
            "errors/generic.html",
            {"status_code": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        # Log the real cause for developers; show the user a generic page so no
        # stack trace or SQL ever reaches the browser.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return render(request, "errors/500.html", status_code=500)
