"""Password hashing and CSRF token helpers."""

import hmac
import secrets

import bcrypt

# bcrypt truncates anything past 72 bytes; reject longer input explicitly rather
# than silently ignoring the tail of a user's password.
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt hash for `plain_password`."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode())
    except (ValueError, TypeError):
        # Malformed/legacy hash — treat as a failed login, never a 500.
        return False


# --- CSRF ---------------------------------------------------------------------

CSRF_SESSION_KEY = "csrf_token"
CSRF_FIELD_NAME = "csrf_token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_token_is_valid(session_token: str, submitted_token: str) -> bool:
    """Compare the session token with the one posted by the form."""
    if not session_token or not submitted_token:
        return False
    return hmac.compare_digest(session_token, submitted_token)
