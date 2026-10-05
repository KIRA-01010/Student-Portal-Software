"""Alembic environment.

Pulls the database URL and model metadata from the application itself so there
is a single source of truth for both.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database.base import Base
from app.models import (  # noqa: F401  (registers tables on Base.metadata)
    AuthSession,
    CourseGrade,
    LoginFailure,
    Student,
    StudentRecord,
    Teacher,
)

config = context.config

# Use the app's database unless the caller (e.g. app.database.migrate, or a
# test) already supplied a URL. "%" is doubled because ConfigParser treats it
# as an interpolation character.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# The CLI (`alembic ...`) gets alembic.ini's logging setup. When migrations run
# inside the app (app.database.migrate) that flag is off, so Alembic doesn't
# replace the host application's logging configuration.
if config.config_file_name is not None and config.attributes.get(
    "configure_logging", True
):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER most things in place; batch mode rewrites tables.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
