"""Server-side login sessions.

The signed cookie only carries an opaque random token. Who the visitor is — and
whether they are still signed in — is decided by the `auth_sessions` table:

  * logging out deletes the row, so a copied cookie is worthless afterwards;
  * rows expire on their own (`SESSION_MAX_AGE`);
  * forging a cookie is not enough even if SECRET_KEY leaks, because a valid
    token must also exist in the database;
  * "sign out everywhere" (e.g. after a password change) is one DELETE.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import settings
from app.models.security import AuthSession
from app.utils.clock import as_utc, utcnow

SESSION_TOKEN_KEY = "auth_token"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _current_token(request: Request) -> Optional[str]:
    token = request.session.get(SESSION_TOKEN_KEY)
    return token if isinstance(token, str) and token else None


def purge_expired(db: Session) -> None:
    """Drop sessions past their expiry so the table doesn't grow forever."""
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    db.commit()


def start_session(request: Request, db: Session, *, role: str, account_id: int) -> None:
    """Create a session row and put its token in the (fresh) cookie session."""
    purge_expired(db)
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        AuthSession(
            token_hash=_hash(token),
            role=role,
            account_id=account_id,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.session_max_age),
        )
    )
    db.commit()
    request.session[SESSION_TOKEN_KEY] = token


def resolve_account_id(request: Request, db: Session, *, role: str) -> Optional[int]:
    """The account id behind this request's session for `role`, or ``None``."""
    token = _current_token(request)
    if token is None:
        return None

    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash(token)))
    if row is None:
        # Revoked (logged out elsewhere), expired-and-purged, or forged.
        request.session.pop(SESSION_TOKEN_KEY, None)
        return None

    if as_utc(row.expires_at) <= utcnow():
        db.delete(row)
        db.commit()
        request.session.pop(SESSION_TOKEN_KEY, None)
        return None

    # A valid session for the *other* role is simply not a session here.
    return row.account_id if row.role == role else None


def end_session(request: Request, db: Session) -> None:
    """Revoke this request's session server-side and wipe the cookie session."""
    token = _current_token(request)
    if token is not None:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash(token)))
        db.commit()
    request.session.clear()


def end_all_sessions(db: Session, *, role: str, account_id: int) -> None:
    """Sign an account out of every browser (use after a password change)."""
    db.execute(
        delete(AuthSession).where(
            AuthSession.role == role, AuthSession.account_id == account_id
        )
    )
    db.commit()
