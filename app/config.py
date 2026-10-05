"""Application configuration.

All settings are read from environment variables (or a local `.env` file) so the
app can move between dev / staging / prod without code changes.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the project root (…/student-portal)
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"

# Values that are public (they ship in this repo / .env.example), so they must
# never sign session cookies outside local development.
INSECURE_SECRET_KEYS = frozenset(
    {
        "dev-only-insecure-secret-change-me",
        "change-me-to-a-long-random-string",
    }
)
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -------------------------------------------------------------
    app_name: str = "Student Portal"
    debug: bool = False

    # --- Security ------------------------------------------------------------
    # Signs the session cookie. MUST be overridden in production via env var.
    secret_key: str = "dev-only-insecure-secret-change-me"
    session_cookie_name: str = "student_portal_session"
    session_max_age: int = 60 * 60 * 24 * 7  # 7 days ("remember until logout")
    # Send the cookie over HTTPS only. Leave False for local http:// dev.
    session_https_only: bool = False

    # Brute-force protection (see app.services.login_throttle). A visitor may
    # fail this many sign-ins for one account from one address inside the
    # window before being locked out; wider limits apply per account (any
    # address) and per address (any account) as multiples of this number.
    login_max_attempts: int = Field(default=5, ge=1)
    login_lockout_seconds: int = Field(default=15 * 60, ge=1)

    # --- Database ------------------------------------------------------------
    # Swappable: point at Postgres/MySQL later without touching the code.
    database_url: str = f"sqlite:///{BASE_DIR / 'student_portal.db'}"

    @model_validator(mode="after")
    def _require_strong_secret_key_outside_debug(self) -> "Settings":
        """Fail closed: refuse to start in production with a guessable key.

        The session cookie is signed with SECRET_KEY. Anyone who knows the key
        can forge a cookie for any student or teacher id, so a placeholder
        value here is equivalent to having no authentication at all.
        """
        if self.debug:
            return self
        if (
            self.secret_key in INSECURE_SECRET_KEYS
            or len(self.secret_key) < MIN_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                "SECRET_KEY is missing, a placeholder, or shorter than "
                f"{MIN_SECRET_KEY_LENGTH} characters, and DEBUG is off. Set a "
                "strong random SECRET_KEY in .env or the environment. Generate "
                'one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(48))"'
            )
        return self

    # --- Paths ---------------------------------------------------------------
    @property
    def templates_dir(self) -> Path:
        return APP_DIR / "templates"

    @property
    def static_dir(self) -> Path:
        return APP_DIR / "static"

    @property
    def upload_dir(self) -> Path:
        return BASE_DIR / "uploads"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (import this, not the class)."""
    return Settings()


settings = get_settings()
