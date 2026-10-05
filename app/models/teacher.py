"""Teacher ORM model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.account import AccountMixin


class TeacherStatus:
    """Where a teacher account is in the approval process."""

    PENDING = "pending"  # registered, waiting for an administrator
    APPROVED = "approved"  # may sign in and manage records
    REJECTED = "rejected"  # declined or revoked; may not sign in

    ALL = (PENDING, APPROVED, REJECTED)


class Teacher(Base, AccountMixin):
    """A registered teacher account.

    Anyone can *register* as a teacher, but a new account starts out
    ``pending`` and cannot sign in until an administrator approves it.
    Administrators are ordinary teacher accounts with ``is_admin`` set; that flag
    can only be changed from the command line (``python -m app.cli``), never
    through the website, so the site itself offers no path to escalate rights.
    """

    __tablename__ = "teachers"

    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # --- Approval ------------------------------------------------------------
    # Fails closed: a row inserted without an explicit status is "pending".
    status: Mapped[str] = mapped_column(
        String(10),
        default=TeacherStatus.PENDING,
        server_default=TeacherStatus.PENDING,
        nullable=False,
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Who last approved/rejected this account and when. `reviewed_by_id` is
    # empty when the decision came from the command line. No foreign key: it
    # is a historical note, and SQLite cannot add one to an existing table.
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    courses = relationship("Course", back_populates="teacher", cascade="all, delete-orphan")

    # --- Convenience ---------------------------------------------------------
    @property
    def is_approved(self) -> bool:
        return self.status == TeacherStatus.APPROVED

    @property
    def is_pending(self) -> bool:
        return self.status == TeacherStatus.PENDING

    @property
    def is_rejected(self) -> bool:
        return self.status == TeacherStatus.REJECTED
