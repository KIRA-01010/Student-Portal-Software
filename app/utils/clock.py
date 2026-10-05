"""UTC time helpers shared by the security code."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Treat a naive datetime (what SQLite hands back) as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
