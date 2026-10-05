"""Security bookkeeping tables: server-side login sessions and failed logins."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.utils.clock import utcnow


class AuthSession(Base):
    """One signed-in browser session.

    The browser's cookie carries a random token; only its SHA-256 hash is
    stored here, so a leaked database does not hand out live sessions. Deleting
    the row is what actually signs someone out — copying the cookie beforehand
    does not help an attacker.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # "student" | "teacher". No foreign key: one table serves both account types.
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    __table_args__ = (Index("ix_auth_sessions_role_account_id", "role", "account_id"),)


class LoginFailure(Base):
    """One failed sign-in attempt, kept only long enough to rate-limit."""

    __tablename__ = "login_failures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    # Lower-cased what the visitor typed — recorded whether or not such an
    # account exists, so throttling behaves identically for both.
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_login_failures_role_identifier", "role", "identifier"),
        Index("ix_login_failures_ip", "ip"),
    )
