"""Columns and behaviour shared by every login-owning account type.

Students and teachers are separate tables (their rules differ: teachers need
approval, students don't) but they were near-copies of each other. Everything
they have in common lives here once; `Student` and `Teacher` add only what is
specific to them.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import TimestampMixin


class AccountMixin(TimestampMixin):
    """Identity, credentials and login bookkeeping for one account."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)

    # Uniqueness is enforced at the DB level as well as in the service layer,
    # which closes the race between "check if taken" and "insert".
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Convenience ---------------------------------------------------------
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self) -> str:
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} id={self.id} username={self.username!r}>"
