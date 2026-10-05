"""Reusable, framework-agnostic field validators.

Every function returns an error message (str) or ``None`` when the value is
acceptable, which keeps the form schemas in `app.schemas` declarative.
"""

import re
from typing import Optional

from email_validator import EmailNotValidError, validate_email

from app.utils.security import MAX_PASSWORD_BYTES

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")

MIN_PASSWORD_LENGTH = 8


def clean(value: Optional[str]) -> str:
    """Trim whitespace and normalise ``None`` to an empty string."""
    return (value or "").strip()


def validate_required(value: str, label: str) -> Optional[str]:
    if not value:
        return f"{label} is required."
    return None


def validate_name(value: str, label: str) -> Optional[str]:
    if error := validate_required(value, label):
        return error
    if len(value) > 80:
        return f"{label} must be 80 characters or fewer."
    return None


def validate_email_address(value: str) -> Optional[str]:
    """Check the address is syntactically valid (no DNS lookup)."""
    if error := validate_required(value, "Email"):
        return error
    if len(value) > 255:
        return "Email must be 255 characters or fewer."
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return "Please enter a valid email address."
    return None


def validate_username(value: str) -> Optional[str]:
    if error := validate_required(value, "Username"):
        return error
    if not USERNAME_RE.match(value):
        return (
            "Username must be 3-50 characters and may only contain letters, "
            "numbers, dots, underscores and hyphens."
        )
    return None


def validate_password(value: str) -> Optional[str]:
    if error := validate_required(value, "Password"):
        return error
    if len(value) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password is too long (maximum {MAX_PASSWORD_BYTES} bytes)."
    return None


def validate_password_confirmation(password: str, confirmation: str) -> Optional[str]:
    if not confirmation:
        return "Please confirm your password."
    if password != confirmation:
        return "Passwords do not match."
    return None


# --- Teacher module: academic records -----------------------------------------

MIN_SEMESTER = 1
MAX_SEMESTER = 8
MIN_CREDIT_HOURS = 1
MAX_CREDIT_HOURS = 6
REGISTRATION_NUMBER_RE = re.compile(r"^\d{8}$")


def validate_registration_number(value: str) -> Optional[str]:
    if error := validate_required(value, "Registration number"):
        return error
    if not REGISTRATION_NUMBER_RE.match(value):
        return "Registration number must be exactly 8 digits."
    return None


def validate_department(value: str) -> Optional[str]:
    if error := validate_required(value, "Department"):
        return error
    if len(value) > 120:
        return "Department must be 120 characters or fewer."
    return None


def validate_course_name(value: str) -> Optional[str]:
    if error := validate_required(value, "Course name"):
        return error
    if len(value) > 150:
        return "Course name must be 150 characters or fewer."
    return None


def _validate_int_range(value: str, label: str, minimum: int, maximum: int) -> Optional[str]:
    if error := validate_required(value, label):
        return error
    try:
        parsed = int(value)
    except ValueError:
        return f"{label} must be a whole number."
    if parsed < minimum or parsed > maximum:
        return f"{label} must be between {minimum} and {maximum}."
    return None


def validate_semester(value: str) -> Optional[str]:
    return _validate_int_range(value, "Semester", MIN_SEMESTER, MAX_SEMESTER)


def validate_credit_hours(value: str) -> Optional[str]:
    return _validate_int_range(value, "Credit hours", MIN_CREDIT_HOURS, MAX_CREDIT_HOURS)


def validate_grade(value: str) -> Optional[str]:
    from app.services.cgpa_service import GRADE_POINTS

    if error := validate_required(value, "Grade"):
        return error
    if value not in GRADE_POINTS:
        return f"Grade must be one of: {', '.join(GRADE_POINTS)}."
    return None
