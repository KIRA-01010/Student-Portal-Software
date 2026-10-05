"""Run Alembic migrations from inside the application.

Alembic is the *only* thing that creates or changes tables. Earlier versions of
this project also called `Base.metadata.create_all()` on startup, which builds
tables without recording a migration version — so a later `alembic upgrade
head` crashed with "table students already exists". `upgrade_to_head()` fixes
that by adopting such databases (see `_adopt_unversioned_database`) and then
applying whatever migrations are still missing.
"""

import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import BASE_DIR, settings

logger = logging.getLogger("student_portal")

# Which tables each revision (cumulatively) contains, newest first. Used to tell
# which revision an unversioned database was built at. Add a line here whenever
# a migration creates a table. Migrations that only add columns (such as 0004)
# are deliberately absent: an adopted database is stamped at the newest
# table-creating revision it matches, and `upgrade` then adds the columns.
_REVISION_TABLES = [
    ("0006", {"students", "teachers", "student_records", "course_grades",
              "auth_sessions", "login_failures", "record_shares"}),
    ("0003", {"students", "teachers", "student_records", "course_grades",
              "auth_sessions", "login_failures"}),
    ("0002", {"students", "teachers", "student_records", "course_grades"}),
    ("0001", {"students"}),
]


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(Path(BASE_DIR) / "alembic.ini"))
    # Absolute, so this works no matter which directory the app is started from.
    cfg.set_main_option("script_location", str(Path(BASE_DIR) / "migrations"))
    # ConfigParser treats "%" specially (URL-encoded passwords contain it).
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    # Keep alembic.ini from reconfiguring the application's logging (env.py).
    cfg.attributes["configure_logging"] = False
    return cfg


def _adopt_unversioned_database(cfg: Config, database_url: str) -> None:
    """Give a pre-Alembic database a version stamp instead of re-creating it.

    A database that already has our tables but no recorded version was built by
    the old `create_all()` startup hook. Its schema matches the migrations, so
    we record which revision it corresponds to and let Alembic carry on from
    there. Brand-new (empty) and properly versioned databases are left alone.

    "No recorded version" includes an `alembic_version` table with no rows:
    running `alembic upgrade head` against such a database used to fail on the
    first CREATE TABLE, but only *after* Alembic had already created that empty
    table — so anyone who tried the CLI first is in this state.
    """
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            has_version = "alembic_version" in tables and (
                conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() or 0
            ) > 0
    finally:
        engine.dispose()

    if has_version or "students" not in tables:
        return

    # Stamp the newest revision whose tables are ALL present; `upgrade` then
    # creates whatever is missing. (Never stamp "head" blindly: a database from
    # an older release would be marked up to date without its new tables.)
    revision = next(rev for rev, needed in _REVISION_TABLES if needed <= tables)
    command.stamp(cfg, revision)
    logger.info("Adopted existing database (stamped at %s).", revision)


def upgrade_to_head(database_url: Optional[str] = None) -> None:
    """Bring the database schema up to date. Safe to call repeatedly."""
    url = database_url or settings.database_url
    cfg = _alembic_config(url)
    _adopt_unversioned_database(cfg, url)
    command.upgrade(cfg, "head")
