"""Data-access helpers shared by every account type (student, teacher, ...).

Every query goes through the ORM with bound parameters, so user input can never
be interpolated into SQL. `student_service` and `teacher_service` are thin
bindings of this class to their model.
"""

from datetime import datetime, timezone
from typing import Any, Generic, Optional, Type, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

Account = TypeVar("Account")


class AccountRepository(Generic[Account]):
    def __init__(self, model: Type[Account]) -> None:
        self.model = model

    def get_by_id(self, db: Session, account_id: int) -> Optional[Account]:
        return db.get(self.model, account_id)

    def get_by_email(self, db: Session, email: str) -> Optional[Account]:
        stmt = select(self.model).where(
            func.lower(self.model.email) == email.strip().lower()
        )
        return db.scalars(stmt).first()

    def get_by_username(self, db: Session, username: str) -> Optional[Account]:
        stmt = select(self.model).where(
            func.lower(self.model.username) == username.strip().lower()
        )
        return db.scalars(stmt).first()

    def get_by_identifier(self, db: Session, identifier: str) -> Optional[Account]:
        """Look an account up by *either* email or username (case-insensitive)."""
        value = identifier.strip().lower()
        stmt = select(self.model).where(
            or_(
                func.lower(self.model.email) == value,
                func.lower(self.model.username) == value,
            )
        )
        return db.scalars(stmt).first()

    def email_exists(self, db: Session, email: str) -> bool:
        return self.get_by_email(db, email) is not None

    def username_exists(self, db: Session, username: str) -> bool:
        return self.get_by_username(db, username) is not None

    def create(self, db: Session, **fields: Any) -> Account:
        """Persist a new account. Caller is responsible for validation."""
        account = self.model(**fields)
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    def touch_last_login(self, db: Session, account: Account) -> Account:
        """Record the current time as the account's most recent login."""
        account.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(account)
        return account
