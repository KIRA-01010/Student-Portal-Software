"""Test-data builders (imported by the tests as `sample_data`).

Every builder returns *fresh, unique* values (a random tag is baked into names,
usernames, e-mails and registration numbers), so tests never collide with each
other or with data left behind by an earlier run.
"""

import uuid

# Satisfies the portal's rule (8+ characters, at most 72 bytes).
PASSWORD = "Passw0rd!123"


def unique_tag(length: int = 8) -> str:
    """Short lower-case hex string, e.g. 'a3f9c21b'."""
    return uuid.uuid4().hex[:length]


def student_data(**overrides) -> dict:
    """A valid administrator-created student payload."""
    tag = unique_tag()
    data = {
        "first_name": "Selenium",
        "last_name": f"Student{tag}",
        "email": f"student.{tag}@example.com",
        "registration_number": f"{int(tag, 16) % 100000000:08d}",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "department": "Computer Science",
        "season": "Fall",
        "academic_year": "2026",
        "current_semester": "3",
        "entry_type": "Regular",
    }
    data["username"] = data["registration_number"]
    data.update(overrides)
    return data


def teacher_data(**overrides) -> dict:
    """A valid teacher registration payload."""
    tag = unique_tag()
    data = {
        "first_name": "Selenium",
        "last_name": f"Teacher{tag}",
        "email": f"teacher.{tag}@example.com",
        "username": f"tch_{tag}",
        "department": "Computer Science",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    data.update(overrides)
    return data


def full_name(data: dict) -> str:
    return f"{data['first_name']} {data['last_name']}"


def record_data(tag: str = None, **overrides) -> dict:
    """A valid student record created with an administrator-created student."""
    tag = tag or unique_tag()
    data = {
        "registration_number": f"{int(tag, 16) % 100000000:08d}",
        "first_name": f"Alice{tag}",
        "last_name": f"Anderson{tag}",
        "department": "Computer Science",
        "current_semester": "3",
    }
    data.update(overrides)
    return data


def seed_records(tag: str) -> list:
    """Three distinguishable records that all share `tag` (for search tests)."""
    return [
        record_data(tag, registration_number=f"REG-{tag}-A", first_name=f"Alice{tag}",
                    last_name=f"Anderson{tag}", department="Computer Science",
                    current_semester="1"),
        record_data(tag, registration_number=f"REG-{tag}-B", first_name=f"Bilal{tag}",
                    last_name=f"Baker{tag}", department="Mathematics",
                    current_semester="4"),
        record_data(tag, registration_number=f"REG-{tag}-C", first_name=f"Chloe{tag}",
                    last_name=f"Clark{tag}", department="Physics",
                    current_semester="8"),
    ]
