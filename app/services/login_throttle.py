"""Brute-force protection for the sign-in forms.

Failed attempts are stored in the database (not in memory) so the limits hold
across restarts and across several worker processes. Three sliding windows are
checked, each one guarding against a different attack:

  1. same account + same address      -> one client hammering one account
  2. same account, any address        -> guessing spread over many addresses
  3. same address, any account        -> password spraying / account probing

Scope 1 uses the configured limit (`LOGIN_MAX_ATTEMPTS`); the wider scopes use
multiples of it so a shared network (a campus, say) is not locked out by a few
typos. Because scope 1 includes the address, a stranger typing wrong passwords
for *your* username only locks *themselves* out of it.

Everything is keyed on what the visitor typed, whether or not such an account
exists, so a lockout reveals nothing about which accounts are real.
"""

from datetime import datetime, timedelta
from math import ceil
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.security import LoginFailure
from app.services.exceptions import LoginThrottledError
from app.utils.clock import as_utc, utcnow

ACCOUNT_LIMIT_MULTIPLIER = 4  # scope 2
ADDRESS_LIMIT_MULTIPLIER = 10  # scope 3


def normalise_identifier(identifier: str) -> str:
    return identifier.strip().lower()[:255]


def _window() -> timedelta:
    return timedelta(seconds=settings.login_lockout_seconds)


def _scopes(role: str, identifier: str, ip: str) -> List[Tuple[object, int]]:
    limit = settings.login_max_attempts
    return [
        (
            and_(
                LoginFailure.role == role,
                LoginFailure.identifier == identifier,
                LoginFailure.ip == ip,
            ),
            limit,
        ),
        (
            and_(LoginFailure.role == role, LoginFailure.identifier == identifier),
            limit * ACCOUNT_LIMIT_MULTIPLIER,
        ),
        (LoginFailure.ip == ip, limit * ADDRESS_LIMIT_MULTIPLIER),
    ]


def _seconds_blocked(db: Session, condition, limit: int, now: datetime) -> int:
    """How long until this scope is back under `limit` (0 = not blocked).

    The window slides: once the `limit`-th most recent failure is older than the
    window, only `limit - 1` remain in it and the next attempt is allowed.
    """
    recent = list(
        db.scalars(
            select(LoginFailure.attempted_at)
            .where(condition, LoginFailure.attempted_at > now - _window())
            .order_by(LoginFailure.attempted_at.desc())
            .limit(limit)
        )
    )
    if len(recent) < limit:
        return 0
    frees_up_at = as_utc(recent[-1]) + _window()
    return max(1, ceil((frees_up_at - now).total_seconds()))


def _blocked_for(
    db: Session, role: str, identifier: str, ip: str, now: datetime
) -> int:
    return max(
        _seconds_blocked(db, condition, limit, now)
        for condition, limit in _scopes(role, identifier, ip)
    )


def ensure_allowed(
    db: Session,
    *,
    role: str,
    identifier: str,
    ip: str,
    now: Optional[datetime] = None,
) -> None:
    """Raise `LoginThrottledError` if this visitor is currently locked out."""
    now = now or utcnow()
    wait = _blocked_for(db, role, normalise_identifier(identifier), ip, now)
    if wait:
        raise LoginThrottledError(wait)


def record_failure(
    db: Session,
    *,
    role: str,
    identifier: str,
    ip: str,
    now: Optional[datetime] = None,
) -> None:
    """Remember a failed attempt; raise `LoginThrottledError` if it tips the limit."""
    now = now or utcnow()
    identifier = normalise_identifier(identifier)

    # Rows older than the window can never count again — drop them as we go.
    db.execute(delete(LoginFailure).where(LoginFailure.attempted_at < now - _window()))
    db.add(LoginFailure(role=role, identifier=identifier, ip=ip, attempted_at=now))
    db.commit()

    wait = _blocked_for(db, role, identifier, ip, now)
    if wait:
        raise LoginThrottledError(wait)


def clear_failures(db: Session, *, role: str, identifier: str, ip: str) -> None:
    """A successful sign-in wipes this visitor's own failed attempts."""
    db.execute(
        delete(LoginFailure).where(
            LoginFailure.role == role,
            LoginFailure.identifier == normalise_identifier(identifier),
            LoginFailure.ip == ip,
        )
    )
    db.commit()
