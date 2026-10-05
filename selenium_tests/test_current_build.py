"""Current-build browser contract tests.

These are intentionally small route and UI checks. They replace the former
registration/record CRUD suite, whose workflows no longer exist in this build.
"""

import pytest
from selenium.webdriver.common.by import By


PUBLIC_PAGES = [
    ("student-login", "/login", "Student sign in"),
    ("teacher-login", "/teacher/login", "Teacher sign in"),
    ("teacher-register", "/teacher/register", "Create your teacher account"),
]

ANONYMOUS_STUDENT_PAGES = [
    "/dashboard", "/grades", "/profile", "/courses",
    "/assignments", "/assignments/1", "/dashboard?tab=overview",
    "/grades?semester=1", "/profile?view=details", "/courses?active=1",
    "/assignments?status=open", "/assignments/999/submission",
]

ANONYMOUS_TEACHER_PAGES = [
    "/teacher/dashboard", "/teacher/students", "/teacher/students/new",
    "/teacher/courses", "/teacher/assignments", "/teacher/students/1",
    "/teacher/students/1/edit", "/teacher/students/1/delete",
    "/teacher/students/1/courses/new",
    "/teacher/students?search=", "/teacher/students?scope=all",
    "/teacher/students?department=Computer%20Science",
]

STUDENT_PAGES = [
    ("dashboard", "/dashboard", "Welcome to Student Portal"),
    ("grades", "/grades", "My grades"),
    ("profile", "/profile", "Profile"),
    ("courses", "/courses", "Courses"),
    ("dashboard-query", "/dashboard?tab=overview", "Welcome to Student Portal"),
    ("grades-query", "/grades?semester=1", "My grades"),
    ("profile-query", "/profile?view=details", "Profile"),
    ("courses-query", "/courses?active=1", "Courses"),
    ("assignments", "/assignments", "Assignments"),
    ("assignments-query", "/assignments?status=open", "Assignments"),
    ("dashboard-fragment", "/dashboard#summary", "Welcome to Student Portal"),
    ("grades-fragment", "/grades#results", "My grades"),
]

TEACHER_PAGES = [
    "/teacher/dashboard", "/teacher/students", "/teacher/courses",
    "/teacher/assignments", "/teacher/students?scope=mine",
    "/teacher/students?scope=all", "/teacher/dashboard?view=summary",
    "/teacher/courses?active=1", "/teacher/assignments?status=open",
    "/teacher/students?search=student", "/teacher/students?semester=1",
    "/teacher/students?department=Computer%20Science",
]

ADMIN_PAGES = [
    "/admin/teachers", "/admin/students", "/admin/courses",
    "/admin/students?season=Fall", "/admin/students?academic_year=2026",
    "/admin/students?semester=1", "/admin/students?department=Computer%20Science",
    "/admin/courses?archived=0",
    "/admin/teachers?status=pending",
]


@pytest.mark.parametrize("name,path,heading", PUBLIC_PAGES, ids=[item[0] for item in PUBLIC_PAGES])
def test_public_page_contract(driver, base_url, name, path, heading):
    driver.get(f"{base_url}{path}")

    assert driver.find_element(By.CSS_SELECTOR, "main h1").text.strip() == heading


@pytest.mark.parametrize("path", ANONYMOUS_STUDENT_PAGES)
def test_anonymous_student_page_redirects_to_login(driver, base_url, path):
    driver.get(f"{base_url}{path}")

    assert driver.current_url.split("?", 1)[0].rstrip("/").endswith("/login")


@pytest.mark.parametrize("path", ANONYMOUS_TEACHER_PAGES)
def test_anonymous_teacher_page_redirects_to_teacher_login(driver, base_url, path):
    driver.get(f"{base_url}{path}")

    assert driver.current_url.split("?", 1)[0].rstrip("/").endswith("/teacher/login")


@pytest.mark.parametrize("name,path,heading", STUDENT_PAGES, ids=[item[0] for item in STUDENT_PAGES])
def test_signed_in_student_page_contract(driver, base_url, student_session, name, path, heading):
    driver.get(f"{base_url}{path}")

    assert driver.current_url.split("?", 1)[0].rstrip("/").endswith(path.split("?", 1)[0])
    assert heading in driver.find_element(By.TAG_NAME, "main").text


@pytest.mark.parametrize("path", TEACHER_PAGES)
def test_signed_in_teacher_page_contract(driver, base_url, teacher_session, path):
    driver.get(f"{base_url}{path}")

    assert driver.current_url.split("?", 1)[0].rstrip("/").endswith(path.split("?", 1)[0])
    assert driver.find_element(By.TAG_NAME, "main").is_displayed()


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_signed_in_admin_page_contract(driver, base_url, teacher_session, path):
    driver.get(f"{base_url}{path}")

    assert driver.current_url.split("?", 1)[0].rstrip("/").endswith(path.split("?", 1)[0])
    assert driver.find_element(By.TAG_NAME, "main").is_displayed()


@pytest.mark.parametrize(
    "path,field_names",
    [
        ("/login", ("identifier", "password")),
        ("/teacher/login", ("identifier", "password")),
        ("/teacher/register", ("first_name", "last_name", "email", "username")),
        ("/teacher/register", ("password", "confirm_password")),
        ("/login", ("csrf_token",)),
        ("/teacher/login", ("csrf_token",)),
        ("/teacher/register", ("department",)),
        ("/teacher/register", ("csrf_token",)),
    ],
    ids=["student-login-fields", "teacher-login-fields", "teacher-name-fields", "teacher-password-fields", "student-csrf", "teacher-csrf", "teacher-department", "register-csrf"],
)
def test_auth_form_contract(driver, base_url, path, field_names):
    driver.get(f"{base_url}{path}")

    for field_name in field_names:
        element = driver.find_element(By.NAME, field_name)
        assert element.is_displayed() or field_name == "csrf_token"
