# Student Portal

A full-stack student management portal built with **FastAPI**, **SQLAlchemy 2.0**, **Jinja2** and
**Bootstrap 5**, with role-based access for **Students, Teachers and Administrators**.
It covers admin-managed student accounts, a course catalog with automatic enrollment,
assignment submissions (PDF/image uploads with deadline tracking), CGPA/SGPA grade records,
record sharing between teachers, and a security layer with server-side sessions, CSRF
protection, bcrypt hashing and login rate-limiting. The code follows a service-layer
architecture with Alembic migrations and automated tests.

## Live Demo

**https://student-portal-software.onrender.com/**

| Role | Sign in at | Login | Password |
|---|---|---|---|
| Student | `/login` | `20250001` | `DemoStudent#2026` |
| Teacher | `/teacher/login` | `demo_teacher` | `DemoTeacher#2026` |
| Admin | `/teacher/login` | `demo_admin` | `DemoAdmin#2026` |

Notes:
- Hosted on a free tier: after about 15 minutes idle the first load can take up to a minute.
- Demo data (including uploaded files) resets whenever the server restarts.
- These are public demo accounts. Please don't enter real personal information.

---

## Features

| Area | What's included |
|---|---|
| **Roles** | Student, Teacher and Administrator, each with its own permissions. Students sign in at `/login`, staff at `/teacher/login`. |
| **Student accounts** | Created by an administrator, with no self-registration. Students sign in with their 8-digit registration number, and each student gets one linked academic record automatically. |
| **Teacher approval** | Teachers can register, but a new account is *pending* and cannot sign in until an administrator approves it on the **Teacher accounts** page. Administrators are set from the command line only. See *Teacher accounts and administrators*. |
| **Course catalog** | Administrators create courses by season, academic year, semester and department. Matching students are enrolled automatically, teachers claim the courses they teach, and courses can be archived or restored. |
| **Assignments** | Teachers create assignments with deadlines. Students upload PDF or image submissions, and each submission is flagged on time or late. |
| **Grades** | CGPA and SGPA are computed live from letter grades and credit hours. Students see their own record read-only; the owner, shared teachers and administrators manage grades. See *Student grades*. |
| **Shared records & admin access** | A record has one owner; the owner can share it with other approved teachers, who then view and edit its details and grades. Administrators can open every record and hand a record to a new owner. See *Sharing records and administrator access*. |
| **Sessions** | Server-side sessions: the `HttpOnly`, `SameSite=Lax` cookie holds only a random token whose hash is stored in the database, so logging out really ends access (a copied cookie stops working). 7-day cap; a fresh session is issued on every login to prevent fixation. |
| **Validation** | Bootstrap client-side validation *and* full server-side re-validation. Submitted values are preserved on error (never passwords). |
| **Security** | bcrypt hashing, per-session CSRF tokens on every form, login rate-limiting, protected routes, ORM-only queries (no string-built SQL), autoescaped templates, generic error pages. |
| **UX** | Success/error alerts, submit-button loading spinners, show/hide password toggles, mobile → desktop responsive layout. |

---

## Quick start

```bash
# 1. Clone and enter the project
git clone https://github.com/KIRA-01010/Student-Portal-Software.git
cd Student-Portal-Software

# 2. Create and activate a virtual environment (Python 3.12 recommended)
# Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell):
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Configure local development
cp .env.example .env
# Keep DEBUG=true for local development.

# 5. (Optional) Load the demo accounts shown in "Live Demo" above
alembic upgrade head
python seed_demo.py

# 6. Run
python main.py
```

Open <http://127.0.0.1:8000> — you'll be redirected to the student sign-in page. Staff sign
in at `/teacher/login`. If you loaded the demo data, use the logins from the **Live Demo**
table above. Without it, teachers can register and wait for administrator approval, and
administrators create student accounts.

Alternative run command with autoreload:

```bash
uvicorn main:app --reload
```

Interactive API docs (debug mode only): <http://127.0.0.1:8000/docs>

---

## Database & migrations

**Alembic is the only thing that creates or changes tables.** With `DEBUG=true` (local
development), `python main.py` / `uvicorn main:app` applies any pending migrations on
startup, so a fresh checkout — or a pull that adds a migration — just works. The database
file is `student_portal.db` in the project root.

With `DEBUG=false` the app never touches the schema; run `alembic upgrade head` as an
explicit deploy step (see *Before deploying*).

Alembic reads its URL and metadata straight from `app.config` / `app.models`, so there is a
single source of truth. You can also drive it by hand:

```bash
alembic upgrade head            # apply migrations
alembic downgrade base          # roll everything back
alembic revision --autogenerate -m "add courses table"   # after adding a model
```

**Databases created by older versions.** Earlier versions built tables with
`create_all()`, which left no migration history, so `alembic upgrade head` failed with
`table students already exists`. Starting the app once (debug mode) fixes this: it detects
such a database, records which migration it corresponds to, and keeps all your data. After
that the `alembic` commands work normally. If you would rather do it by hand:
`alembic stamp head`.

**Switching databases** — set `DATABASE_URL` in `.env`; no code changes required:

```bash
DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/student_portal"
```

### Student model

Student accounts are created by an administrator (see `app/services/student_service.py`).

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `registration_number` | String(8) | Unique, indexed; the 8-digit number students sign in with |
| `first_name` | String(80) | Required |
| `last_name` | String(80) | Required |
| `username` | String(50) | Unique, indexed; kept for backwards compatibility and set to the registration number |
| `email` | String(255) | Unique, indexed, stored lower-case |
| `password_hash` | String(255) | bcrypt |
| `department` | String(120) | With season, year and semester, decides which courses the student is enrolled in |
| `season` | String(10) | `Fall` or `Spring` |
| `academic_year` | Integer | Year of the offering |
| `current_semester` | Integer | 1–8, defaults to 1 |
| `entry_type` | String(10) | `Regular` or `Lateral` |
| `last_login_at` | DateTime | Nullable |
| `created_at` | DateTime | Set by the database |
| `updated_at` | DateTime | Maintained by the database on update |

Migrations `0001`–`0009` build the schema; `alembic upgrade head` applies all of them.

---

## Teacher accounts and administrators

Teacher registration is open, but it does not grant access by itself:

- A new teacher account is **pending**. Signing in with the right password shows *"waiting
  for administrator approval"* and creates no session; a wrong password gets the usual generic
  error, so the account's state is only revealed to someone who knows the password.
- An **administrator** approves or rejects sign-ups at **Teacher accounts** (`/admin/teachers`,
  linked in the navbar for admins). Rejecting — or revoking an approved teacher — signs them out
  of every browser immediately, and can be undone by approving them again.
- Administrators are ordinary teacher accounts with an admin flag. **The flag can only be set from
  the command line**, never through the website, so no request can escalate anyone's rights.
  Administrator accounts can't be rejected or changed from the web pages either.

```bash
python -m app.cli list                # every teacher: status and role
python -m app.cli promote <username>  # make an administrator (also approves the account)
python -m app.cli demote <username>   # back to an ordinary teacher
```

**Creating the first administrator:** register a teacher account on the site (`/teacher/register`),
then run `python -m app.cli promote <that username>`. In development the command brings the
database schema up to date first; with `DEBUG=false` run `alembic upgrade head` beforehand.
For a local demo, `python seed_demo.py` instead creates an approved administrator
(`demo_admin`) for you.

**Upgrading an existing installation:** migration `0004` marks every teacher who already exists as
*approved*, so nobody is locked out, and makes nobody an administrator. Run
`python -m app.cli list` afterwards and reject anyone you don't recognise — until this update,
anyone could have created a teacher account.

---

## Student grades

Each student has exactly one academic record. **It is created automatically, and linked to the
student's account, when an administrator creates the student.** A student sees only the record
linked to their own account.

- **Viewing (student):** **Grades** in the navbar shows the record's CGPA, current semester
  and every course grouped by semester with its SGPA; the dashboard shows a summary card.
  Everything is read-only, and grades are computed live, so an edit by staff appears on the
  next page load.
- **Editing (staff):** only the record's owner, a teacher it has been shared with, or an
  administrator can add, change or remove grades. A teacher who can see a student only because
  the student is enrolled in one of their courses has view-only access.
- **Older records:** records that predate automatic linking can still be linked by their owner
  or an administrator: open a record → *Student portal access* → enter the student's
  **username or email** → *Link account*. *Change link* points the record at a different
  account (the previous student loses access at once) and *Unlink* removes access.
- **Why students can't claim records:** registration numbers are not secret, so letting a
  student "claim" a record by typing one would let anyone who knows a number read that
  student's grades.
- **Safeguards:** each student account can be linked to **one** record (enforced by a unique
  database index, so two staff members racing to link the same account cannot both succeed);
  the "already linked" message never reveals whose record it is; and if the account's name
  differs from the record's name the user gets a warning, since a typo would show one student
  another's grades. The student page takes no record id at all — the record is looked up from
  the signed-in student's own id — so there is nothing in a URL to tamper with.

**Upgrading:** migration `0005` adds the unique index. Nothing was linkable before, so no
existing data is affected and no record is linked automatically: after upgrading an older
database, link each student's record from its page.

---

## Sharing records and administrator access

Each record has exactly **one owner** — the teacher or administrator who created it. Registration numbers stay
unique across all teachers (a student has one number), so two teachers work with the same
student by **sharing the record**, not by creating it twice.

| | Owner | Shared teacher | Administrator | Any other teacher |
|---|:---:|:---:|:---:|:---:|
| See it in the students list, open it | ✔ | ✔ | ✔ (via *All teachers*) | 404 |
| Edit its details, add / change / remove grades | ✔ | ✔ | ✔ | 404 |
| Delete it, link / unlink a student portal account | ✔ | 403 | ✔ | 404 |
| Share it with, or remove, other teachers | ✔ | 403 | ✔ | 404 |
| Hand it to a different owner | 403 | 403 | ✔ | 404 |

- **Sharing (owner or administrator):** open a record → *Teachers with access* → enter the
  colleague's **username or email** → *Share record*. Only **approved** teachers can be added;
  a pending, rejected or unknown account gets the same "no approved teacher" message, so the
  form reveals nothing about who has registered. *Remove* takes access away immediately.
- **Shared teachers** see the record in their list with a *Shared with you* badge and in their
  dashboard. They cannot delete it, link a portal account (privacy: that decides who sees the
  grades) or change who else has access — those buttons are not shown, and the URLs answer 403.
  Teachers with no access get a 404, so a record's existence is never revealed to them.
- **Administrators:** the students list has a **My students / All teachers** switch. *All
  teachers* shows every record with its owner (search keeps the switch). The default view is
  still the administrator's own records, so nothing changes until they ask.
- **Handing over ownership (administrators only):** on the record page, *Hand over ownership*
  → the new owner's username or email. The previous owner **loses all access** unless the new
  owner shares the record back; collaborators keep theirs. If the new owner was already a
  collaborator, that entry is dropped — an owner never also appears as a collaborator.
- **Deleting** a record removes its shares and grades with it.

**Upgrading:** migration `0006` adds the `record_shares` table. Nothing is shared
automatically, so upgrading changes nobody's access. In development it is applied on startup;
otherwise run `alembic upgrade head`.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers authentication, CSRF enforcement, role-based access, grades, courses and
assignments. Tests run against an in-memory database and never touch `student_portal.db`.
Browser tests (Selenium) live in `selenium_tests/`, with their dependencies in
`requirements-selenium.txt`.

---

## Project structure

```
Student-Portal-Software/
├── app/
│   ├── __init__.py            # application factory: middleware, routes, error handlers
│   ├── cli.py                 # command-line administration (list / promote / demote)
│   ├── config.py              # env-driven settings (pydantic-settings)
│   ├── database/
│   │   ├── base.py            # declarative Base + created_at/updated_at mixin
│   │   ├── migrate.py         # runs Alembic migrations from inside the app
│   │   └── session.py         # engine, SessionLocal, get_db dependency
│   ├── models/                # account, student, teacher, student_record, course, security
│   ├── routes/                # controllers — thin, no business logic
│   │   ├── auth.py            # student sign-in / sign-out
│   │   ├── teacher_auth.py    # teacher register / sign-in / sign-out
│   │   ├── account_flow.py    # the shared register / sign-in page flow
│   │   ├── dashboard.py       # student dashboard, grades, profile
│   │   ├── teacher_dashboard.py
│   │   ├── teacher_students.py# academic records, grades, sharing
│   │   ├── courses.py         # student course view
│   │   ├── assignments.py     # student and teacher assignment workflows
│   │   ├── admin.py           # teachers, students and course catalog (admins only)
│   │   └── pages.py           # /, /healthz
│   ├── schemas/               # form objects + server-side validation rules
│   ├── services/              # business logic — reusable and testable
│   │   ├── account_auth.py    # authentication shared by every account type
│   │   ├── auth_service.py    # student authentication
│   │   ├── teacher_auth_service.py
│   │   ├── session_service.py # server-side login sessions
│   │   ├── login_throttle.py  # brute-force protection
│   │   ├── student_service.py # administrator-managed student accounts
│   │   ├── teacher_service.py / teacher_admin_service.py
│   │   ├── student_record_service.py  # record access rules and grades
│   │   ├── cgpa_service.py    # CGPA / SGPA calculation
│   │   ├── course_service.py  # catalog, enrollment, assignments, submissions
│   │   └── exceptions.py      # domain errors
│   ├── utils/
│   │   ├── security.py        # bcrypt hashing, CSRF tokens
│   │   ├── validators.py      # field-level validation helpers
│   │   ├── dependencies.py    # require_student / require_teacher / require_admin / verify_csrf
│   │   ├── templating.py      # Jinja env, flash messages, shared context
│   │   └── clock.py, network.py, exceptions.py
│   ├── templates/             # base.html, partials/, auth/, dashboard/, teacher/, admin/, errors/
│   └── static/
│       ├── css/styles.css     # thin theme layer over Bootstrap
│       └── js/main.js         # validation, loading states, password toggles
├── migrations/                # Alembic (0001–0009)
├── tests/                     # pytest suite
├── selenium_tests/            # browser tests
├── main.py                    # entry point
├── seed_demo.py               # demo accounts and sample data (idempotent)
├── wipe_data.py               # one-time reset: wipes all data except admin accounts
├── requirements.txt
├── requirements-dev.txt
├── requirements-selenium.txt
└── .env.example
```

### Layering

```
routes  →  services  →  models
   ↓          ↓
schemas    utils
```

Routes parse the request and render; **services own the business rules**; models own
persistence. Nothing above the service layer touches the ORM, which is what makes the
services reusable from a future JSON API, CLI or background job.

---

## Configuration

All settings come from environment variables or `.env` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `Student Portal` | Shown in the navbar, titles and footer |
| `DEBUG` | `false` | Development mode: autoreload, `/docs`, migrations applied on startup |
| `SECRET_KEY` | dev placeholder | Signs the session cookie. **With `DEBUG=false` the app refuses to start** unless this is a random value of 32+ characters (not a placeholder) |
| `SESSION_COOKIE_NAME` | `student_portal_session` | Cookie name |
| `SESSION_MAX_AGE` | `604800` | Session lifetime in seconds (7 days), enforced server-side |
| `SESSION_HTTPS_ONLY` | `false` | Set `true` when serving over HTTPS |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed sign-ins per account per address before lockout |
| `LOGIN_LOCKOUT_SECONDS` | `900` | Length of the sliding window (and so the maximum lockout) |
| `DATABASE_URL` | local SQLite file | Any SQLAlchemy URL |

---

---

## Security notes

- **Passwords** — bcrypt with a per-password salt; inputs longer than bcrypt's 72-byte
  limit are rejected rather than silently truncated.
- **CSRF** — a per-session token is embedded in every form and compared with
  `hmac.compare_digest`. Combined with `SameSite=Lax`, cross-site posts are blocked twice.
- **Sessions** — the cookie carries a random token; only its SHA-256 hash is stored, in the
  `auth_sessions` table. Logging out deletes that row, so a cookie copied beforehand is
  useless. Identity comes from the row, not the cookie, so even a leaked `SECRET_KEY` cannot be
  used to forge a login. Sessions expire after `SESSION_MAX_AGE`, are reissued on login
  (session-fixation defence), and `session_service.end_all_sessions()` signs an account out of
  every browser (use it when adding password change).
- **Brute force** — failed sign-ins are recorded in `login_failures` and checked in three
  sliding windows: same account from the same address (`LOGIN_MAX_ATTEMPTS`, default 5 per
  15 minutes), the same account from any address (4x that), and the same address against any
  account (10x). While locked out, even the correct password is refused (HTTP 429 with
  `Retry-After`). Unknown usernames are throttled identically, so the lockout leaks nothing;
  because the first window includes the address, a stranger cannot lock *you* out. Students and
  teachers are throttled separately. Limits live in the database, so they hold across restarts
  and multiple workers.
- **Teacher sign-up and admin rights** — teacher accounts start *pending* and are re-checked on
  every request, so revoking access takes effect at once even for someone already signed in.
  A row inserted without a status defaults to pending (fails closed). Admin rights are read
  from the database on every request and can only be granted by `python -m app.cli`.
- **Grade privacy** — a student is shown the record linked to *their own account* and
  nothing else; the lookup uses the session's student id, never a request parameter. Linking
  and unlinking (for older records) is limited to the record's owner or an administrator,
  ownership-checked and CSRF-protected.
- **Record access** — every record lookup goes through `student_record_service.get_accessible`
  (owner, shared teacher or administrator, else 404) and owner-only actions additionally
  require `can_manage`; the rules live in one service module rather than in each route. The
  administrator flag is read from the database on every request, so removing it takes effect
  at once, and the *All teachers* list scope is ignored for non-administrators.
- **Enumeration** — login failures return one generic message, and a dummy hash is
  verified when the identifier is unknown so response timing does not leak whether an
  account exists.
- **SQL injection** — every query is built through SQLAlchemy with bound parameters.
- **XSS** — Jinja2 autoescaping is on; no user input is rendered with `|safe`.
- **Error handling** — unhandled exceptions are logged server-side and shown to the user
  as a generic page; no stack traces, SQL or internals reach the browser.

### Before deploying

1. Set `DEBUG=false` and a strong `SECRET_KEY`
   (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). The app will not start
   with a missing or placeholder key — anyone who knows the key can forge a login cookie.
2. Set `SESSION_HTTPS_ONLY=true` and terminate TLS in front of the app.
3. Point `DATABASE_URL` at a managed database and run `alembic upgrade head` (the app does
   not migrate by itself when `DEBUG=false`).
4. Serve with a process manager, e.g.
   `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4`.
5. Behind a reverse proxy, add `--proxy-headers --forwarded-allow-ips=<proxy address>` so
   the app sees each visitor's real IP. Without it every visitor appears to come from the
   proxy and the per-address lockout limits are shared by everyone.
6. Create your first administrator (`python -m app.cli promote <username>`, after registering
   that teacher account). Until you do, new teachers stay pending and nobody can approve them.

### Example: the live demo on Render

The public demo runs on Render's free tier with:

- **Build command:** `pip install -r requirements.txt`
- **Start command:**
  `alembic upgrade head && python seed_demo.py && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
- **Environment variables:** `DEBUG=false`, a generated `SECRET_KEY`, `SESSION_HTTPS_ONLY=true`,
  `PYTHON_VERSION=3.12.3`

`seed_demo.py` is safe to run on every start: it creates the demo administrator, teacher,
students, courses, grades and assignments only if they don't exist yet. The demo uses SQLite
on an ephemeral disk, so its data resets whenever the server restarts. The demo passwords are
public by design; never reuse them anywhere real.

---

## Extending the portal

Adding a feature (for example, attendance) follows the same four steps every time:

1. **Model** — add `app/models/attendance.py`, export it from `app/models/__init__.py`.
2. **Migration** — `alembic revision --autogenerate -m "add attendance"`.
3. **Service** — put the queries and rules in `app/services/attendance_service.py`.
4. **Route + template** — create `app/routes/attendance.py` and register it in
   `app/routes/__init__.py`; add templates under `app/templates/attendance/`.

Protecting a new page is one dependency (`require_student`, `require_teacher` or `require_admin`):

```python
@router.get("/attendance")
def attendance_page(request: Request, student: Student = Depends(require_student)):
    return render(request, "attendance/index.html", {"student": student})
```

Any form you add just needs `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
and `Depends(verify_csrf)` on the POST handler.

---

## Notes

- Timestamps are stored and displayed in UTC.
- Bootstrap 5.3 and Bootstrap Icons load from a CDN with SRI hashes; vendor them locally
  if the deployment must work offline.
