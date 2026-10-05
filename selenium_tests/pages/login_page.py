"""Student and teacher sign-in pages."""

from .base_page import BasePage


class LoginPage(BasePage):
    path = "/login"

    def sign_in(self, identifier: str, password: str):
        """Fill in the 'Email or Username' and 'Password' fields and submit."""
        self.fill_fields({"identifier": identifier, "password": password})
        self.submit()
        return self

    def error_message(self) -> str:
        """The message the server shows inside the sign-in card."""
        return self.form_alert()


class TeacherLoginPage(LoginPage):
    path = "/teacher/login"
