"""Command-line administration.

    python -m app.cli list                 # every teacher, their status and role
    python -m app.cli promote <username>   # make a teacher an administrator
    python -m app.cli demote <username>    # back to an ordinary teacher

This is the only way to grant administrator rights. There is deliberately no
web page or form for it: rights that a request can grant are rights an attacker
can try to request. Whoever can run this command already controls the server.

`promote` also approves the account, so it is how you create the very first
administrator: register as a teacher on the site, then promote that username.
"""

import argparse
import sys
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.teacher import Teacher
from app.services import teacher_admin_service
from app.services.exceptions import AdminActionError


def _role(teacher: Teacher) -> str:
    return "admin" if teacher.is_admin else "teacher"


def _table(teachers: List[Teacher]) -> str:
    if not teachers:
        return "No teacher accounts yet."
    rows = [("ID", "USERNAME", "NAME", "STATUS", "ROLE")]
    rows += [
        (str(t.id), t.username, t.full_name, t.status, _role(t)) for t in teachers
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
        for row in rows
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Student Portal administration."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show every teacher account")
    for name, text in (
        ("promote", "make a teacher an administrator (and approve them)"),
        ("demote", "remove administrator rights"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("username", help="the teacher's username")
    return parser


def run(argv: Sequence[str], db: Session, out=None) -> int:
    """Execute one command against `db`. Returns the process exit code."""
    out = out or sys.stdout
    args = build_parser().parse_args(argv)

    try:
        if args.command == "list":
            print(_table(teacher_admin_service.list_all(db)), file=out)
        elif args.command == "promote":
            teacher = teacher_admin_service.promote(db, args.username)
            print(f"{teacher.username} is now an administrator.", file=out)
        elif args.command == "demote":
            teacher = teacher_admin_service.demote(db, args.username)
            print(f"{teacher.username} is now an ordinary teacher.", file=out)
    except AdminActionError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Imported here so `--help` and the tests don't need a configured database.
    from app.config import settings
    from app.database.migrate import upgrade_to_head
    from app.database.session import SessionLocal

    # Same rule as main.py: in development, bring the schema up to date first,
    # so this works right after pulling an update. Elsewhere the operator runs
    # `alembic upgrade head` as an explicit step.
    if settings.debug:
        upgrade_to_head()

    with SessionLocal() as db:
        return run(sys.argv[1:] if argv is None else argv, db)


if __name__ == "__main__":
    raise SystemExit(main())
