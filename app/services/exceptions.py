"""Domain-level exceptions raised by the service layer.

Routes translate these into friendly messages; nothing here ever leaks a
database or stack-trace detail to the user.
"""

from typing import Dict, Optional


class ServiceError(Exception):
    """Base class for expected, user-facing failures."""

    message = "Something went wrong. Please try again."

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class FieldValidationError(ServiceError):
    """One or more fields failed a server-side rule (e.g. email taken)."""

    def __init__(self, errors: Dict[str, str], message: Optional[str] = None):
        self.errors = errors
        super().__init__(message or "Please correct the highlighted fields.")


class InvalidCredentialsError(ServiceError):
    """Wrong identifier or password.

    The message is deliberately vague so it cannot be used to enumerate
    which accounts exist.
    """

    message = "Invalid username/password."


class LoginThrottledError(ServiceError):
    """Too many failed sign-ins; further attempts are refused for a while.

    Raised for unknown identifiers exactly as for real ones, so the lockout
    cannot be used to discover which accounts exist.
    """

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        minutes = max(1, -(-self.retry_after_seconds // 60))  # ceiling division
        unit = "minute" if minutes == 1 else "minutes"
        super().__init__(
            f"Too many failed sign-in attempts. Please try again in {minutes} {unit}."
        )


class AccountNotApprovedError(ServiceError):
    """The password was right, but the account may not sign in (yet).

    Only raised *after* the credentials check, so it never tells a stranger
    whether an account exists or what state it is in.
    """

    PENDING_MESSAGE = (
        "Your account is waiting for administrator approval. "
        "You will be able to sign in once it has been approved."
    )
    REJECTED_MESSAGE = (
        "Your account has not been approved. Please contact an administrator."
    )

    def __init__(self, status: str):
        self.status = status
        super().__init__(
            self.PENDING_MESSAGE if status == "pending" else self.REJECTED_MESSAGE
        )


class AdminActionError(ServiceError):
    """An administrator action that is not allowed (e.g. on another admin)."""


class RecordLinkError(ServiceError):
    """A student record could not be linked to the requested student account."""


class RecordShareError(ServiceError):
    """A record could not be shared with, or handed over to, that teacher."""

