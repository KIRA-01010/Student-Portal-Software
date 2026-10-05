"""Focused tests for the current administrator-created-student workflow."""

import re

import pytest
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy import select

from app.database.migrate import upgrade_to_head
from app.models import Teacher
from app.services import student_service
from tests.conftest import approve_teacher, csrf_for, db_of, teacher_register_payload


CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def register_teacher(client, *, username="teacher", email=None, admin=False, approve=True):
    email = email or f"{username}@example.com"
    payload = teacher_register_payload(username=username, email=email)
    payload["csrf_token"] = csrf_for(client, "/teacher/register")
    response = client.post("/teacher/register", data=payload, follow_redirects=False)
    assert response.status_code == 303
    if approve:
        approve_teacher(client, username, admin=admin)
    return payload


def sign_in_teacher(client, credentials):
    payload = {
        "identifier": credentials["username"],
        "password": credentials["password"],
        "csrf_token": csrf_for(client, "/teacher/login"),
    }
    response = client.post("/teacher/login", data=payload, follow_redirects=False)
    return response


def create_student(client, admin_teacher, *, registration_number="12345678"):
    db = db_of(client)
    return student_service.create_admin_student(
        db,
        registration_number=registration_number,
        first_name="Ada",
        last_name="Lovelace",
        email=f"student.{registration_number}@example.com",
        password="supersecret1",
        department="Computer Science",
        season="Fall",
        academic_year=2026,
        current_semester=3,
        entry_type="Regular",
        created_by_teacher_id=admin_teacher.id,
    )


def test_public_auth_pages_and_health(client):
    for response in (client.get("/healthz"), client.get("/login"), client.get("/teacher/login"), client.get("/teacher/register")):
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("path", ["/dashboard", "/grades", "/profile", "/courses", "/assignments"])
def test_anonymous_student_pages_redirect_to_login(client, path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


@pytest.mark.parametrize(
    "path",
    ["/teacher/dashboard", "/teacher/students", "/teacher/courses", "/teacher/assignments"],
)
def test_anonymous_teacher_pages_redirect_to_teacher_login(client, path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].endswith("/teacher/login")


def test_teacher_must_be_approved_before_sign_in(client):
    credentials = register_teacher(client, username="pending", approve=False)
    client.cookies.clear()

    response = sign_in_teacher(client, credentials)

    assert response.status_code == 403


def test_admin_creates_student_and_student_can_sign_in(client):
    credentials = register_teacher(client, username="admin", admin=True)
    assert sign_in_teacher(client, credentials).status_code == 303
    admin = db_of(client).scalar(select(Teacher).where(Teacher.username == "admin"))
    student = create_student(client, admin)
    client.cookies.clear()

    response = client.post(
        "/login",
        data={
            "identifier": student.registration_number,
            "password": "supersecret1",
            "csrf_token": csrf_for(client, "/login"),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/dashboard")


def test_admin_can_open_student_management_pages(client):
    credentials = register_teacher(client, username="admin", admin=True)
    assert sign_in_teacher(client, credentials).status_code == 303

    for path in ("/admin/teachers", "/admin/students", "/admin/courses"):
        assert client.get(path).status_code == 200


def test_non_admin_teacher_cannot_open_admin_pages(client):
    credentials = register_teacher(client, username="teacher")
    assert sign_in_teacher(client, credentials).status_code == 303

    assert client.get("/admin/students").status_code == 403


def test_teacher_student_creation_is_forbidden(client):
    credentials = register_teacher(client, username="teacher")
    assert sign_in_teacher(client, credentials).status_code == 303

    assert client.get("/teacher/students/new").status_code == 403


def test_migrations_reach_current_head(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'portal.db'}"
    upgrade_to_head(database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("select version_num from alembic_version")).scalar_one()
            assert version == "0009"
            assert MigrationContext.configure(connection).get_current_heads() == ("0009",)
    finally:
        engine.dispose()
