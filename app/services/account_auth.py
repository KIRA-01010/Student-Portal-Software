"""Authentication use-cases shared by every account type.

Students and teachers sign in identically — same password checks, same
sessions, same rate limiting — so that behaviour lives here exactly once and a
security fix cannot be applied to one role and forgotten for the other.
`auth_service` (students) and `teacher_auth_service` (teachers) are thin
bindings that supply the role name and repository.

Routes stay thin — they parse the request, call in here, and render.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.services import login_throttle, session_service
from app.services.account_repository import AccountRepository
from app.services.exceptions import (
    FieldValidationError,
    InvalidCredentialsError,
    ServiceError,
)
from app.utils.security import hash_password, verify_password

PREVIOUS_LOGIN_KEY = "previous_login_at"

# A pre-computed hash of a throwaway password. When the identifier does not
# exist we still verify against it so that "unknown user" and "wrong password"
# take the same amount of time (blocks user enumeration by timing).
_DUMMY_HASH = hash_password("timing-attack-mitigation-placeholder")


@dataclass(frozen=True)
class AccountKind:
    """What differs between account types: a name and where accounts live."""

    role: str  # "student" | "teacher" — stored on sessions and failed logins
    repository: AccountRepository
    # Optional gate for accounts that exist but may not be signed in (e.g. a
    # teacher awaiting approval). Raises a ServiceError to refuse. Checked when
    # signing in *and* on every request, so revoking access takes effect at once.
    access_check: Optional[Callable[[Any], None]] = None


# --- Registration -------------------------------------------------------------


def register(db: Session, kind: AccountKind, form: Any, **extra_fields: Any) -> Any:
    """Validate and persist a new account.

    `form` needs ``validate()`` plus first_name / last_name / email / username /
    password attributes; `extra_fields` carries role-specific columns.

    Raises:
        FieldValidationError: if any field is invalid or already taken.
    """
    repo = kind.repository
    errors = form.validate()

    # Uniqueness checks only run once the field itself is well-formed.
    if "email" not in errors and repo.email_exists(db, form.email):
        errors["email"] = "Email already exists."
    if "username" not in errors and repo.username_exists(db, form.username):
        errors["username"] = "Username already exists."

    if errors:
        raise FieldValidationError(errors)

    try:
        return repo.create(
            db,
            first_name=form.first_name,
            last_name=form.last_name,
            email=form.email,
            username=form.username,
            password_hash=hash_password(form.password),
            **extra_fields,
        )
    except IntegrityError:
        # Two concurrent registrations can pass the checks above and collide on
        # the unique index. The DB is the source of truth, so recover cleanly.
        db.rollback()
        errors = {}
        if repo.email_exists(db, form.email):
            errors["email"] = "Email already exists."
        if repo.username_exists(db, form.username):
            errors["username"] = "Username already exists."
        raise FieldValidationError(
            errors or {"username": "That account could not be created."}
        )


# --- Login / logout -----------------------------------------------------------


def authenticate(db: Session, kind: AccountKind, form: Any, *, client_ip: str) -> Any:
    """Return the account matching the submitted credentials.

    Raises:
        LoginThrottledError: too many recent failures for this visitor. Checked
            *before* the password, so a locked-out visitor learns nothing from
            trying more guesses (even a correct one is refused).
        InvalidCredentialsError: unknown identifier or bad password.
        ServiceError: the password was right but ``kind.access_check`` refuses
            the account (for teachers: not approved yet).
    """
    login_throttle.ensure_allowed(
        db, role=kind.role, identifier=form.identifier, ip=client_ip
    )

    account = kind.repository.get_by_identifier(db, form.identifier)
    stored_hash = account.password_hash if account is not None else _DUMMY_HASH
    password_ok = verify_password(form.password, stored_hash)  # constant work

    if account is None or not password_ok:
        # May itself raise LoginThrottledError if this failure hits the limit.
        login_throttle.record_failure(
            db, role=kind.role, identifier=form.identifier, ip=client_ip
        )
        raise InvalidCredentialsError()

    login_throttle.clear_failures(
        db, role=kind.role, identifier=form.identifier, ip=client_ip
    )
    # Credentials were correct, so it is safe to say *why* access is refused.
    if kind.access_check is not None:
        kind.access_check(account)
    return account


def start_login(request: Request, db: Session, kind: AccountKind, account: Any) -> None:
    """Sign `account` in: fresh server-side session, fresh cookie session."""
    previous_login = account.last_login_at
    # Revoke whatever session this browser already had and start from a blank
    # cookie — prevents session fixation and leaves no stale session behind.
    session_service.end_session(request, db)
    session_service.start_session(request, db, role=kind.role, account_id=account.id)
    request.session[PREVIOUS_LOGIN_KEY] = (
        previous_login.isoformat() if previous_login else None
    )
    kind.repository.touch_last_login(db, account)


def end_login(request: Request, db: Session) -> None:
    """Sign out: delete the server-side session and wipe the cookie."""
    session_service.end_session(request, db)


def current_account(request: Request, db: Session, kind: AccountKind) -> Optional[Any]:
    """Resolve the signed-in account from the session, or ``None``."""
    account_id = session_service.resolve_account_id(request, db, role=kind.role)
    if account_id is None:
        return None

    account = kind.repository.get_by_id(db, account_id)
    if account is None:
        # Account deleted while the session was still alive.
        session_service.end_session(request, db)
        return None

    if kind.access_check is not None:
        try:
            kind.access_check(account)
        except ServiceError:
            # Access was withdrawn while the session was still alive.
            session_service.end_session(request, db)
            return None
    return account


def get_previous_login(request: Request) -> Optional[datetime]:
    """The login timestamp *before* the current session started."""
    raw = request.session.get(PREVIOUS_LOGIN_KEY)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
