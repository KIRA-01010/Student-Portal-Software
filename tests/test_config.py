"""Settings: production must never boot with a guessable SECRET_KEY."""

import pytest
from pydantic import ValidationError

from app.config import INSECURE_SECRET_KEYS, Settings

STRONG_KEY = "k" * 48


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Make sure the developer's real .env / environment can't leak in."""
    for name in ("DEBUG", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_debug_defaults_to_off():
    settings = make(secret_key=STRONG_KEY)
    assert settings.debug is False


def test_debug_mode_allows_the_default_key():
    settings = make(debug=True)
    assert settings.secret_key in INSECURE_SECRET_KEYS


def test_production_rejects_the_default_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(debug=False)


@pytest.mark.parametrize("placeholder", sorted(INSECURE_SECRET_KEYS))
def test_production_rejects_every_known_placeholder(placeholder):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(debug=False, secret_key=placeholder)


def test_production_rejects_a_short_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(debug=False, secret_key="short-but-unique")


def test_production_accepts_a_strong_key():
    settings = make(debug=False, secret_key=STRONG_KEY)
    assert settings.secret_key == STRONG_KEY


def test_error_message_tells_you_how_to_fix_it():
    with pytest.raises(ValidationError) as excinfo:
        make(debug=False)
    assert "secrets.token_urlsafe" in str(excinfo.value)


def test_login_throttle_defaults():
    settings = make(debug=True)
    assert settings.login_max_attempts == 5
    assert settings.login_lockout_seconds == 15 * 60


@pytest.mark.parametrize("field", ["login_max_attempts", "login_lockout_seconds"])
def test_login_throttle_limits_must_be_positive(field):
    with pytest.raises(ValidationError):
        make(debug=True, **{field: 0})
