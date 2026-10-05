"""Form objects for the teacher authentication flows.

Teachers sign in exactly like students, so they share `LoginForm`. Their
registration form is the student one plus an optional department.
"""

from dataclasses import dataclass
from typing import Dict

from app.schemas.auth import LoginForm, RegistrationForm

MAX_DEPARTMENT_LENGTH = 120

# Same fields, same rules: kept as a name so teacher code reads naturally.
TeacherLoginForm = LoginForm


@dataclass
class TeacherRegistrationForm(RegistrationForm):
    department: str = ""

    def validate(self) -> Dict[str, str]:
        errors = super().validate()
        if self.department and len(self.department) > MAX_DEPARTMENT_LENGTH:
            errors["department"] = (
                f"Department must be {MAX_DEPARTMENT_LENGTH} characters or fewer."
            )
        return errors

    def as_form_values(self) -> Dict[str, str]:
        return {**super().as_form_values(), "department": self.department}
