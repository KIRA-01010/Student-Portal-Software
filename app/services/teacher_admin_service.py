"""Administrator use-cases: review teacher sign-ups and manage who is an admin.

Two callers share these rules:

  * the ``/admin`` web pages, which can approve or reject teachers, and
  * the command line (``python -m app.cli``), which is the *only* place the
    admin flag can be set. Keeping promotion off the website means there is no
    request an attacker can craft to gain administrator rights.
"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.teacher import Teacher, TeacherStatus
from app.services import session_service
from app.services.exceptions import AdminActionError
from app.utils.clock import utcnow


# --- Queries ------------------------------------------------------------------


def get_teacher(db: Session, teacher_id: int) -> Optional[Teacher]:
    return db.get(Teacher, teacher_id)


def list_pending(db: Session) -> List[Teacher]:
    """Sign-ups waiting for a decision, oldest first (first come, first served)."""
    stmt = (
        select(Teacher)
        .where(Teacher.status == TeacherStatus.PENDING)
        .order_by(Teacher.created_at, Teacher.id)
    )
    return list(db.scalars(stmt))


def list_reviewed(db: Session) -> List[Teacher]:
    """Everyone who is not waiting: approved and rejected teachers, by name."""
    stmt = (
        select(Teacher)
        .where(Teacher.status != TeacherStatus.PENDING)
        .order_by(Teacher.last_name, Teacher.first_name, Teacher.id)
    )
    return list(db.scalars(stmt))


def pending_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Teacher)
        .where(Teacher.status == TeacherStatus.PENDING)
    ) or 0


# --- Approve / reject (web) ---------------------------------------------------


def _check_can_review(actor: Teacher, target: Teacher) -> None:
    if not actor.is_admin:
        # Routes already require an admin; this keeps the service safe on its own.
        raise AdminActionError("Only administrators can review teacher accounts.")
    if target.is_admin:
        raise AdminActionError(
            "Administrator accounts can't be changed here. "
            "Use the command line (python -m app.cli) instead."
        )


def _record_review(target: Teacher, status: str, reviewer_id: Optional[int]) -> None:
    target.status = status
    target.reviewed_at = utcnow()
    target.reviewed_by_id = reviewer_id


def approve(db: Session, actor: Teacher, target: Teacher) -> Teacher:
    """Let a pending (or previously rejected) teacher sign in."""
    _check_can_review(actor, target)
    if not target.is_approved:
        _record_review(target, TeacherStatus.APPROVED, actor.id)
        db.commit()
        db.refresh(target)
    return target


def reject(db: Session, actor: Teacher, target: Teacher) -> Teacher:
    """Refuse a sign-up, or revoke access from an approved teacher.

    Any browser the teacher is signed in on is signed out immediately.
    """
    _check_can_review(actor, target)
    if not target.is_rejected:
        _record_review(target, TeacherStatus.REJECTED, actor.id)
        db.commit()
        db.refresh(target)
    session_service.end_all_sessions(db, role="teacher", account_id=target.id)
    return target


# --- Admin flag (command line only) ---------------------------------------------


def _by_username(db: Session, username: str) -> Teacher:
    teacher = db.scalar(
        select(Teacher).where(func.lower(Teacher.username) == username.strip().lower())
    )
    if teacher is None:
        raise AdminActionError(f"No teacher with the username {username!r}.")
    return teacher


def promote(db: Session, username: str) -> Teacher:
    """Make a teacher an administrator (and approve them, so they can sign in)."""
    teacher = _by_username(db, username)
    if not teacher.is_approved:
        _record_review(teacher, TeacherStatus.APPROVED, None)
    teacher.is_admin = True
    db.commit()
    db.refresh(teacher)
    return teacher


def demote(db: Session, username: str) -> Teacher:
    """Take administrator rights away. The account stays an ordinary teacher."""
    teacher = _by_username(db, username)
    teacher.is_admin = False
    db.commit()
    db.refresh(teacher)
    return teacher


def list_all(db: Session) -> List[Teacher]:
    """Every teacher, for the command-line overview."""
    return list(db.scalars(select(Teacher).order_by(Teacher.id)))
