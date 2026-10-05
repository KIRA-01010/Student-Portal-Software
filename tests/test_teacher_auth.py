"""End-to-end tests for teacher registration, login, session guards and logout.

Mirrors `tests/test_auth.py`'s structure/style for the teacher module.
"""

from tests.conftest import approve_teacher, csrf_for, teacher_register_payload


def do_register(client, **overrides):
    data = teacher_register_payload(**overrides)
    data["csrf_token"] = csrf_for(client, "/teacher/register")
    return client.post("/teacher/register", data=data, follow_redirects=False)


def register_approved(client, **overrides):
    """Register a teacher and have an administrator approve them."""
    response = do_register(client, **overrides)
    approve_teacher(client, overrides.get("username", "grace"))
    return response


def do_login(client, identifier="grace", password="supersecret1"):
    data = {
        "identifier": identifier,
        "password": password,
        "csrf_token": csrf_for(client, "/teacher/login"),
    }
    return client.post("/teacher/login", data=data, follow_redirects=False)


# --- Registration -------------------------------------------------------------


def test_registration_succeeds_and_redirects_to_login(client):
    response = do_register(client)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/teacher/login")

    login_page = client.get("/teacher/login")
    assert "needs to approve your account" in login_page.text


def test_registration_rejects_duplicate_email(client):
    do_register(client)
    client.cookies.clear()

    response = do_register(client, username="grace2")
    assert response.status_code == 400
    assert "Email already exists." in response.text


def test_registration_rejects_duplicate_username(client):
    do_register(client)
    client.cookies.clear()

    response = do_register(client, email="other@example.com")
    assert response.status_code == 400
    assert "Username already exists." in response.text


def test_registration_rejects_mismatched_passwords(client):
    response = do_register(client, confirm_password="different1")
    assert response.status_code == 400
    assert "Passwords do not match." in response.text


def test_registration_rejects_short_password(client):
    response = do_register(client, password="short1", confirm_password="short1")
    assert response.status_code == 400
    assert "at least 8 characters" in response.text


def test_registration_requires_csrf_token(client):
    response = client.post(
        "/teacher/register", data=teacher_register_payload(), follow_redirects=False
    )
    assert response.status_code == 303  # bounced back with a flash, not created
    assert do_login(client).status_code == 401


# --- Login / session ----------------------------------------------------------


def test_login_with_username_and_with_email(client):
    register_approved(client)
    client.cookies.clear()

    assert do_login(client, identifier="grace").status_code == 303
    client.cookies.clear()
    assert do_login(client, identifier="grace@example.com").status_code == 303


def test_login_rejects_wrong_password(client):
    do_register(client)
    client.cookies.clear()

    response = do_login(client, password="wrongpassword")
    assert response.status_code == 401
    assert "Invalid username/password." in response.text


def test_login_rejects_unknown_user(client):
    response = do_login(client, identifier="nobody")
    assert response.status_code == 401
    assert "Invalid username/password." in response.text


def test_teacher_dashboard_requires_authentication(client):
    response = client.get("/teacher/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/teacher/login")


def test_teacher_dashboard_shows_details_after_login(client):
    register_approved(client)
    client.cookies.clear()
    do_login(client)

    response = client.get("/teacher/dashboard")
    assert response.status_code == 200
    assert "Grace Hopper" in response.text


def test_logout_destroys_session(client):
    register_approved(client)
    client.cookies.clear()
    do_login(client)

    token = csrf_for(client, "/teacher/dashboard")
    response = client.post(
        "/teacher/logout", data={"csrf_token": token}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/teacher/login")

    assert client.get("/teacher/dashboard", follow_redirects=False).status_code == 303


def test_authenticated_teacher_is_redirected_away_from_login(client):
    register_approved(client)
    client.cookies.clear()
    do_login(client)

    response = client.get("/teacher/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/teacher/dashboard")


def test_password_is_hashed_not_stored_in_plaintext(client):
    from app.database.session import get_db
    from app.models import Teacher

    do_register(client)

    db = next(client.app.dependency_overrides[get_db]())
    teacher = db.query(Teacher).one()
    assert teacher.password_hash != "supersecret1"
    assert teacher.password_hash.startswith("$2b$")
