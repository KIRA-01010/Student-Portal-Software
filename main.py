"""Entry point.

Run directly:      python main.py
Or with uvicorn:   uvicorn main:app --reload
"""

import uvicorn

from app import create_app
from app.config import settings
from app.database.migrate import upgrade_to_head

# Local-development convenience: apply any pending Alembic migrations so a fresh
# checkout (or a pull that adds a migration) just works. Alembic is the only
# thing that creates tables. Outside debug mode the schema is never touched
# automatically — deployments run `alembic upgrade head` as an explicit step.
if settings.debug:
    upgrade_to_head()

app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.debug,
    )
