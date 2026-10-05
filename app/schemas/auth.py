"""Authentication form objects."""
from dataclasses import dataclass
from typing import Dict
import re

from app.utils import validators as v


@dataclass
class RegistrationForm:
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    username: str = ""
    password: str = ""
    confirm_password: str = ""

    @classmethod
    def from_raw(cls, first_name: str, last_name: str, email: str, username: str, password: str, confirm_password: str, **extra: str) -> "RegistrationForm":
        return cls(first_name=v.clean(first_name), last_name=v.clean(last_name), email=v.clean(email).lower(), username=v.clean(username).lower(), password=password or "", confirm_password=confirm_password or "", **{name: v.clean(value) for name, value in extra.items()})

    def validate(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if error := v.validate_name(self.first_name, "First name"): errors["first_name"] = error
        if error := v.validate_name(self.last_name, "Last name"): errors["last_name"] = error
        if error := v.validate_email_address(self.email): errors["email"] = error
        if error := v.validate_username(self.username): errors["username"] = error
        if error := v.validate_password(self.password): errors["password"] = error
        elif error := v.validate_password_confirmation(self.password, self.confirm_password): errors["confirm_password"] = error
        return errors

    def as_form_values(self) -> Dict[str, str]:
        return {"first_name": self.first_name, "last_name": self.last_name, "email": self.email, "username": self.username}


@dataclass
class LoginForm:
    identifier: str = ""
    password: str = ""

    @classmethod
    def from_raw(cls, identifier: str, password: str) -> "LoginForm":
        return cls(identifier=v.clean(identifier), password=password or "")

    def validate(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if error := v.validate_required(self.identifier, "Email or username"): errors["identifier"] = error
        if error := v.validate_required(self.password, "Password"): errors["password"] = error
        return errors

    def as_form_values(self) -> Dict[str, str]:
        return {"identifier": self.identifier}


@dataclass
class StudentLoginForm(LoginForm):
    @classmethod
    def from_raw(cls, identifier: str, password: str) -> "StudentLoginForm":
        return cls(identifier=v.clean(identifier), password=password or "")

    def validate(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if not self.identifier:
            errors["identifier"] = "Registration number is required."
        elif not re.fullmatch(r"\d{8}", self.identifier):
            errors["identifier"] = "Registration number must be exactly 8 digits."
        if error := v.validate_required(self.password, "Password"):
            errors["password"] = error
        return errors
