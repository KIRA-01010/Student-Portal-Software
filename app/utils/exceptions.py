"""Transport-level exceptions raised by dependencies and handled in `app`."""


class NotAuthenticatedError(Exception):
    """Raised when a route's session requirement is not met.

    Used for both directions: an anonymous visitor hitting the dashboard, and a
    signed-in student hitting the login page.
    """

    def __init__(self, redirect_to: str = "/login", authenticated: bool = False):
        super().__init__("Authentication requirement not met.")
        self.redirect_to = redirect_to
        self.authenticated = authenticated


class CsrfError(Exception):
    """Raised when a POST is missing or carrying a stale CSRF token."""

    message = "Your session expired. Please try again."
