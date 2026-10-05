"""Data-access helpers for the Teacher model (see `account_repository`)."""

from typing import Optional

from app.models.teacher import Teacher, TeacherStatus
from app.services.account_repository import AccountRepository

repository = AccountRepository(Teacher)

get_by_id = repository.get_by_id
get_by_email = repository.get_by_email
get_by_username = repository.get_by_username
get_by_identifier = repository.get_by_identifier
email_exists = repository.email_exists
username_exists = repository.username_exists
touch_last_login = repository.touch_last_login


def create(
    db,
    *,
    first_name: str,
    last_name: str,
    email: str,
    username: str,
    password_hash: str,
    department: Optional[str] = None,
    status: str = TeacherStatus.PENDING,
) -> Teacher:
    """Persist a new teacher (``pending`` unless told otherwise).

    Caller is responsible for validation.
    """
    return repository.create(
        db,
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=username,
        password_hash=password_hash,
        department=department,
        status=status,
    )
