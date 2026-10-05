"""Test fixtures: an app wired to a throwaway SQLite database."""

import os
import re
from typing import Dict

import bcrypt
import pytest

os.environ.setdefault("DEBUG", "true")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.database.base import Base
from app.database.session import get_db
from app.models import Teacher, TeacherStatus
from app.services import account_auth

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True, scope="session")
def _cheap_bcrypt():
    """Hash with bcrypt cost 4 instead of 12 so the suite runs in seconds.

    Tests that check a login attempt (especially the brute-force ones) verify
    dozens of passwords; at production cost that dominates the run time. The
    algorithm and verification code paths are unchanged. Production code is
    untouched — this only affects the salts generated while testing.
    """
    real_gensalt = bcrypt.gensalt
    original_dummy = account_auth._DUMMY_HASH
    bcrypt.gensalt = lambda rounds=4, prefix=b"2b": real_gensalt(rounds, prefix)
    account_auth._DUMMY_HASH = bcrypt.hashpw(b"placeholder", bcrypt.gensalt()).decode()
    yield
    bcrypt.gensalt = real_gensalt
    account_auth._DUMMY_HASH = original_dummy


@pytest.fixture()
def client():
    """A TestClient backed by an in-memory database, isolated per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection == one in-memory DB
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def csrf_for(client: TestClient, path: str) -> str:
    """Fetch `path` and extract the CSRF token from the rendered form."""
    response = client.get(path)
    match = CSRF_RE.search(response.text)
    assert match, f"no CSRF token found on {path}"
    return match.group(1)


def register_payload(**overrides) -> Dict[str, str]:
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "username": "ada",
        "password": "supersecret1",
        "confirm_password": "supersecret1",
    }
    payload.update(overrides)
    return payload


def teacher_register_payload(**overrides) -> Dict[str, str]:
    payload = {
        "first_name": "Grace",
        "last_name": "Hopper",
        "email": "grace@example.com",
        "username": "grace",
        "department": "Computer Science",
        "password": "supersecret1",
        "confirm_password": "supersecret1",
    }
    payload.update(overrides)
    return payload


def db_of(client: TestClient):
    """A database session bound to the same in-memory database as `client`."""
    return next(client.app.dependency_overrides[get_db]())


def approve_teacher(client: TestClient, username: str = "grace", *, admin: bool = False):
    """Mark an already-registered teacher approved (and optionally an admin).

    New teachers start out pending and cannot sign in, so tests that need a
    working teacher login call this right after registering. It edits the
    database directly, exactly as the command line would.
    """
    db = db_of(client)
    teacher = db.scalar(select(Teacher).where(Teacher.username == username))
    assert teacher is not None, f"no teacher {username!r} to approve"
    teacher.status = TeacherStatus.APPROVED
    if admin:
        teacher.is_admin = True
    db.commit()
    return teacher
