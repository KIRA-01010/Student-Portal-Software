# Selenium automation tests – Student Portal

Browser tests written with **Selenium 4 + pytest** using the **Page Object Model**.
They drive the real portal in a real browser, exactly as a user would.

| Required flow | File | Test cases |
|---|---|---|
| Login | `test_login.py` | TC-LOGIN-01 … 08 |
| Registration | `test_registration.py` | TC-REG-01 … 05 |
| Form validation | `test_form_validation.py` | TC-VAL-01 … 14 |
| Search | `test_search.py` | TC-SEARCH-01 … 08 |
| Add record | `test_add_record.py` | TC-ADD-01 … 05 |
| Update record | `test_update_record.py` | TC-UPD-01 … 05 |
| Delete record | `test_delete_record.py` | TC-DEL-01 … 04 |
| Logout | `test_logout.py` | TC-LOGOUT-01 … 05 |

51 test functions → 68 test runs (some are parametrised). The `TC-…` ids appear in every
docstring – rename them to match the ids in your own test-case document.

> "Record" = a **student record** that a teacher manages under *Teacher → Students*
> (add / edit / delete / search). Students themselves can only register, sign in and view.

---

## Setup (once)

From the project root (`student-portal/`), with your virtual environment active:

```powershell
.venv\Scripts\activate                      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-selenium.txt
```

You also need **Google Chrome** (or Edge / Firefox) installed. Selenium 4.6+ downloads the
matching driver automatically the first time (needs internet once).

## Run

```powershell
pytest selenium_tests                                  # everything, visible browser
pytest selenium_tests/test_login.py                    # one file
pytest selenium_tests -k "search"                      # by name
pytest selenium_tests -m validation                    # by marker (see pytest.ini)
pytest selenium_tests --html=selenium_tests/reports/report.html --self-contained-html
```

Options (environment variables):

| Variable | Values | Default | Meaning |
|---|---|---|---|
| `BROWSER` | `chrome`, `edge`, `firefox` | `chrome` | Browser to drive |
| `BASE_URL` | e.g. `http://127.0.0.1:8000` | *(unset)* | Test a server you started yourself |

PowerShell: `$env:HEADLESS = "1"; pytest selenium_tests`  ·  cmd: `set HEADLESS=1`  ·  bash: `HEADLESS=1 pytest selenium_tests`

### Running from VS Code (nothing to set each time)

The project's `.vscode/` folder makes VS Code use `.venv` and lists both test folders in the
**Testing** panel (flask icon). The variables above are read from **`.vscode/selenium.env`**, so
you set them once — edit `HEADLESS=0` / `HEADLESS=1` there. Or use **Terminal → Run Task…**:
*Selenium: run all (headless)*, *…(visible browser)* or *…current file*. The tasks call `.venv`'s
Python directly and set their own variables, so they work even before an interpreter is picked.

## What happens when you run it

1. **The portal is started for you** (`uvicorn main:app` on a free port) with its **own temporary
   SQLite database**. Your real `student_portal.db` is never touched. The server log is written to
   `selenium_tests/reports/server.log`.
2. **One teacher account** is registered through the UI and then approved with the admin CLI
   (`python -m app.cli promote` followed by `demote`, leaving an ordinary approved teacher). New teachers
   are *pending* by design, so the CRUD tests cannot log in without this step.
3. **Every test gets its own fresh browser** and its own uniquely-named data
   (random tag in usernames, e-mails and registration numbers), so tests are independent and can
   run in any order.
4. **On failure a screenshot** is saved to `selenium_tests/reports/screenshots/`.

If you use `BASE_URL`, the server must run with `DEBUG=true` and use the default database, because
the teacher-approval step runs `python -m app.cli` against the default `student_portal.db`.

## Layout

```
student-portal/
├── requirements-selenium.txt
└── selenium_tests/
    ├── conftest.py            # server + browser + login fixtures, failure screenshots
    ├── sample_data.py         # unique test-data builders
    ├── pytest.ini
    ├── pages/                 # Page Objects: locators + actions, no assertions
    │   ├── base_page.py       #   waits, messages, form/validation helpers, logout
    │   ├── register_page.py   #   student + teacher registration
    │   ├── login_page.py      #   student + teacher sign-in
    │   ├── dashboard_pages.py
    │   └── students_pages.py  #   list/search, add/edit form, detail, delete confirmation
    └── test_*.py              # the test cases (assertions live here)
```

## Design notes

* **Explicit waits only** – no `time.sleep()`, no implicit waits.
* **Locators live in the page objects.** If the HTML changes, fix one place, not every test.
* **Validation is tested twice on purpose.** The portal validates in the browser (Bootstrap/HTML5) *and*
  on the server. Plain tests show what the browser blocks; tests using
  `bypass_client_validation()` push bad data past the browser to prove the server rejects it too.
* **Messages are read with `textContent`**, so tests behave the same whether or not the Bootstrap CSS
  from the CDN loaded.
* Each wrong-password test uses a brand-new account, because the portal locks an
  account after 5 failed sign-ins (`LOGIN_MAX_ATTEMPTS`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `SessionNotCreatedException` / driver error | Update the browser, or try `BROWSER=edge`. First run needs internet for the driver download. |
| `The portal exited while starting up` | Open `selenium_tests/reports/server.log`; usually a missing package – reinstall `requirements.txt`. |
| Every test errors in `teacher_account` | Same log; the CLI approval step failed. Check `python -m app.cli list` works. |
| Tests are slow to start | The page loads Bootstrap from a CDN; offline machines wait for it to time out. |
| A dropdown/logout test flakes on a small window | Keep the browser ≥ 1000 px wide (the suite sets 1400×1000). |
