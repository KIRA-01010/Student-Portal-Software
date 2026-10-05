"""One-time reset: wipes all data except admin accounts.

Deletes, in dependency order: submissions, assignments, enrollments,
courses, course grades, record shares, student records, students, all
login sessions/lockout history, and every teacher account that is NOT
marked is_admin. Admin teacher rows (and their password) are untouched.

Run once from the project root with the venv active:
    python wipe_data.py

BACK UP student_portal.db BEFORE RUNNING THIS. It cannot be undone.
"""
from sqlalchemy import text

from app.database.session import SessionLocal

TABLES_IN_ORDER = [
    "assignment_submissions",
    "assignments",
    "course_enrollments",
    "courses",
    "course_grades",
    "record_shares",
    "student_records",
    "students",
    "auth_sessions",
    "login_failures",
]

db = SessionLocal()
try:
    admin_count = db.execute(text("SELECT COUNT(*) FROM teachers WHERE is_admin = 1")).scalar()
    if not admin_count:
        print("No admin account found — aborting so you don't lock yourself out.")
        raise SystemExit(1)

    confirm = input(
        f"This will permanently delete ALL students, courses, records and sessions, "
        f"and every non-admin teacher, keeping {admin_count} admin account(s). "
        f"Type 'yes' to continue: "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted. Nothing was deleted.")
        raise SystemExit(0)

    for table in TABLES_IN_ORDER:
        db.execute(text(f"DELETE FROM {table}"))
    db.execute(text("DELETE FROM teachers WHERE is_admin = 0"))
    db.commit()
    print("Done. Only admin account(s) remain.")
finally:
    db.close()
