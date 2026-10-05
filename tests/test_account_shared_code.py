"""Students and teachers share one implementation of everything they have in common.

The sign-in flow, the forms and the account columns used to exist twice, so a fix
had to be made in two places and could be forgotten in one. These tests pin the
sharing down; the end-to-end behaviour is covered by the auth and teacher tests.
"""

from dataclasses import fields

import pytest

from app.models import Student, Teacher
from app.models.account import AccountMixin
from app.schemas.auth import LoginForm, RegistrationForm
from app.schemas.teacher_auth import TeacherLoginForm, TeacherRegistrationForm
from app.services import auth_service, teacher_auth_service

ACCOUNT_COLUMNS = {
    "id",
    "first_name",
    "last_name",
    "username",
    "email",
    "password_hash",
    "last_login_at",
    "created_at",
    "updated_at",
}
TEACHER_ONLY_COLUMNS = {"department", "status", "is_admin", "reviewed_at", "reviewed_by_id"}
STUDENT_ONLY_COLUMNS = {
    "registration_number",
    "department",
    "season",
    "academic_year",
    "current_semester",
    "entry_type",
}

RAW = dict(
    first_name="  Ada ",
    last_name=" Lovelace",
    email=" Ada@Example.COM ",
    username=" ADA ",
    password="  keep my spaces  ",
    confirm_password="  keep my spaces  ",
)


# --- Models -----------------------------------------------------------------------


def test_the_account_columns_are_defined_once_and_used_by_both_models():
    assert issubclass(Student, AccountMixin) and issubclass(Teacher, AccountMixin)
    assert set(Student.__table__.columns.keys()) == ACCOUNT_COLUMNS | STUDENT_ONLY_COLUMNS
    assert set(Teacher.__table__.columns.keys()) == ACCOUNT_COLUMNS | TEACHER_ONLY_COLUMNS


@pytest.mark.parametrize("model", [Student, Teacher])
def test_usernames_and_emails_are_unique_and_indexed_on_both_tables(model):
    for name in ("username", "email"):
        column = model.__table__.columns[name]
        assert column.unique and column.index and not column.nullable


@pytest.mark.parametrize("model", [Student, Teacher])
def test_name_helpers_work_the_same_for_both(model):
    account = model(
        first_name="Ada",
        last_name="Lovelace",
        username="ada",
        email="ada@example.com",
        password_hash="x",
    )

    assert account.full_name == "Ada Lovelace"
    assert account.initials == "AL"
    assert model.__name__ in repr(account) and "ada" in repr(account)


# --- Forms ------------------------------------------------------------------------


def test_teachers_sign_in_with_the_very_same_form_as_students():
    assert TeacherLoginForm is LoginForm


def test_the_teacher_registration_form_only_adds_a_department():
    assert issubclass(TeacherRegistrationForm, RegistrationForm)
    added = {f.name for f in fields(TeacherRegistrationForm)} - {
        f.name for f in fields(RegistrationForm)
    }
    assert added == {"department"}


@pytest.mark.parametrize("form_class", [RegistrationForm, TeacherRegistrationForm])
def test_both_registration_forms_trim_and_lowercase_the_same_way(form_class):
    form = form_class.from_raw(**RAW)

    assert form.first_name == "Ada" and form.last_name == "Lovelace"
    assert form.email == "ada@example.com" and form.username == "ada"
    assert form.password == "  keep my spaces  "  # passwords are never trimmed
    assert form.validate() == {}


@pytest.mark.parametrize("form_class", [RegistrationForm, TeacherRegistrationForm])
def test_both_registration_forms_apply_the_same_rules(form_class):
    form = form_class.from_raw(**{**RAW, "email": "nope", "confirm_password": "different"})

    assert set(form.validate()) == {"email", "confirm_password"}


@pytest.mark.parametrize("form_class", [RegistrationForm, TeacherRegistrationForm])
def test_echoed_form_values_never_contain_a_password(form_class):
    values = form_class.from_raw(**RAW).as_form_values()

    assert "password" not in values and "confirm_password" not in values
    assert values["email"] == "ada@example.com"


def test_only_teachers_have_a_department():
    teacher = TeacherRegistrationForm.from_raw(**RAW, department="  Mathematics ")

    assert teacher.department == "Mathematics"
    assert teacher.as_form_values()["department"] == "Mathematics"
    assert "department" not in RegistrationForm.from_raw(**RAW).as_form_values()
    with pytest.raises(TypeError):
        RegistrationForm.from_raw(**RAW, department="Mathematics")


def test_the_department_is_optional_but_capped():
    assert TeacherRegistrationForm.from_raw(**RAW).validate() == {}

    too_long = TeacherRegistrationForm.from_raw(**RAW, department="x" * 121)

    assert too_long.validate() == {
        "department": "Department must be 120 characters or fewer."
    }


# --- Routes -----------------------------------------------------------------------


def test_both_routers_hand_the_sign_in_flow_to_the_shared_code():
    from app.routes import auth, teacher_auth

    portals = {
        "student": (auth.STUDENT_PORTAL, auth_service),
        "teacher": (teacher_auth.TEACHER_PORTAL, teacher_auth_service),
    }
    for portal, service in portals.values():
        assert portal.service is service
        for entry_point in ("register", "authenticate", "login_session", "logout_session"):
            assert callable(getattr(service, entry_point))


def test_each_portal_points_at_its_own_pages():
    from app.routes import auth, teacher_auth

    student, teacher = auth.STUDENT_PORTAL, teacher_auth.TEACHER_PORTAL

    assert student.login_template == "auth/login.html"
    assert teacher.login_template == "teacher/login.html"
    assert student.home_route == "dashboard_page"
    assert teacher.home_route == "teacher_dashboard_page"
    assert student.login_route == "login_page"
    assert teacher.login_route == "teacher_login_page"
    # A new teacher account waits for approval; that is the message that says so.
    assert "approve" in teacher.registered_message
    assert teacher.registered_category == "info"
