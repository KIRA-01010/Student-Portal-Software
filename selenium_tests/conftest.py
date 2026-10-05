"""Shared fixtures for the Selenium suite.

What happens when you run `pytest selenium_tests`:

  1. A throw-away copy of the portal is started with uvicorn on a free port. It
     uses its own SQLite file in a temp folder, so your real `student_portal.db`
     is never touched. (Set BASE_URL to test an already-running server instead.)
  2. One teacher account is registered through the UI and approved from the
     command line - exactly how the README says the first administrator is made.
  3. Every test gets its own fresh browser, so tests cannot affect each other.

Environment variables (all optional):

    BROWSER    chrome (default) | edge | firefox
    BASE_URL   e.g. http://127.0.0.1:8000 - use a server you started yourself
"""

import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from selenium import webdriver

from pages import (
    AdminStudentsPage,
    DashboardPage,
    LoginPage,
    RegisterPage,
    StudentFormPage,
    TeacherDashboardPage,
    TeacherLoginPage,
    TeacherRegisterPage,
)
from sample_data import seed_records, student_data, teacher_data, unique_tag

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
REPORTS_DIR = TESTS_DIR / "reports"
SERVER_START_TIMEOUT = 30  # seconds


# --------------------------------------------------------------------------
# Browser
# --------------------------------------------------------------------------
def create_driver():
    """Start the browser chosen with the BROWSER environment variable."""
    browser = os.getenv("BROWSER", "chrome").lower()
    headless = False

    if browser == "chrome":
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        driver = webdriver.Chrome(options=options)
    elif browser == "edge":
        options = webdriver.EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        driver = webdriver.Edge(options=options)
    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument("-headless")
        driver = webdriver.Firefox(options=options)
    else:
        raise pytest.UsageError(f"Unsupported BROWSER={browser!r} (use chrome, edge or firefox)")

    # A wide window keeps the navbar expanded (Bootstrap collapses it < 992px).
    driver.set_window_size(1400, 1000)
    return driver


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Remember each phase's result so the `driver` fixture can see a failure."""
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())


@pytest.fixture()
def driver(request):
    """A fresh browser per test; a screenshot is saved when the test fails."""
    browser = create_driver()
    try:
        yield browser
    finally:
        report = getattr(request.node, "rep_call", None)
        if report is not None and report.failed:
            shots = REPORTS_DIR / "screenshots"
            shots.mkdir(parents=True, exist_ok=True)
            name = re.sub(r"[^\w.-]+", "_", request.node.name)
            target = shots / f"{name}.png"
            try:
                browser.save_screenshot(str(target))
                print(f"\nScreenshot saved: {target}")
            except Exception as error:  # the browser may already be gone
                print(f"\nCould not take a screenshot: {error}")
        browser.quit()


# --------------------------------------------------------------------------
# Application under test
# --------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_up(url: str, process=None, log_path: Path = None) -> None:
    deadline = time.time() + SERVER_START_TIMEOUT
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            log = log_path.read_text(errors="replace") if log_path else ""
            raise RuntimeError(f"The portal exited while starting up.\n{log[-3000:]}")
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.25)
    raise RuntimeError(f"The portal did not answer {url}/healthz within {SERVER_START_TIMEOUT}s")


@pytest.fixture(scope="session")
def app_env(tmp_path_factory):
    """Environment used to start the portal *and* to run its admin CLI."""
    env = os.environ.copy()
    if not os.getenv("BASE_URL"):
        database = tmp_path_factory.mktemp("portal-db") / "selenium.db"
        env.update(
            {
                "DATABASE_URL": f"sqlite:///{database.as_posix()}",
                "DEBUG": "true",  # applies the Alembic migrations at start-up
                "PYTHONUNBUFFERED": "1",
            }
        )
    return env


@pytest.fixture(scope="session")
def base_url(app_env):
    """Address of the running portal (started here unless BASE_URL is set)."""
    external = os.getenv("BASE_URL")
    if external:
        _wait_until_up(external.rstrip("/"))
        yield external.rstrip("/")
        return

    REPORTS_DIR.mkdir(exist_ok=True)
    log_path = REPORTS_DIR / "server.log"
    url = f"http://127.0.0.1:{_free_port()}"
    port = url.rsplit(":", 1)[1]

    with open(log_path, "w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", port],
            cwd=PROJECT_ROOT,
            env=app_env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_up(url, process, log_path)
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def approve_teacher(env: dict, username: str) -> None:
    """Approve a pending teacher through the admin CLI.

    `promote` approves the account and makes it an administrator.  The current
    build requires an administrator to create student accounts and records.
    """
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "promote", username],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"`app.cli promote {username}` failed:\n{result.stderr or result.stdout}")


# --------------------------------------------------------------------------
# Accounts and pre-built sessions
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def teacher_account(base_url, app_env):
    """An approved teacher: registered through the UI, approved via the CLI."""
    data = teacher_data()
    bootstrap_browser = create_driver()
    try:
        page = TeacherRegisterPage(bootstrap_browser, base_url).open()
        page.register(**data)
        page.wait_for_path("/teacher/login")
    finally:
        bootstrap_browser.quit()
    approve_teacher(app_env, data["username"])
    return data


@pytest.fixture()
def registered_student(driver, base_url, teacher_account):
    """An administrator-created student; the browser is left on /login."""
    data = student_data()
    TeacherLoginPage(driver, base_url).open().sign_in(
        teacher_account["username"], teacher_account["password"]
    )
    TeacherDashboardPage(driver, base_url).wait_for_path("/teacher/dashboard")
    AdminStudentsPage(driver, base_url).open().create(**data)
    driver.get(f"{base_url}/login")
    LoginPage(driver, base_url).wait_for_path("/login")
    return data


@pytest.fixture()
def student_session(driver, base_url, registered_student):
    """A student who is signed in and looking at the dashboard."""
    LoginPage(driver, base_url).sign_in(registered_student["username"], registered_student["password"])
    dashboard = DashboardPage(driver, base_url)
    dashboard.wait_for_path("/dashboard")
    return dashboard


@pytest.fixture()
def teacher_session(driver, base_url, teacher_account):
    """The approved teacher, signed in and looking at the teacher dashboard."""
    TeacherLoginPage(driver, base_url).open().sign_in(
        teacher_account["username"], teacher_account["password"]
    )
    dashboard = TeacherDashboardPage(driver, base_url)
    dashboard.wait_for_path("/teacher/dashboard")
    return dashboard


@pytest.fixture()
def seeded_records(driver, base_url, teacher_session):
    """Three student records (sharing one unique tag) added through the UI."""
    tag = unique_tag()
    records = seed_records(tag)
    for record in records:
        AdminStudentsPage(driver, base_url).open().create_record(record)
    return SimpleNamespace(tag=tag, records=records)
