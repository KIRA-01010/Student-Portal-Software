"""Student and teacher registration pages."""

from .base_page import BasePage


class RegisterPage(BasePage):
    path = "/register"
    FIELDS = ("first_name", "last_name", "email", "username", "password", "confirm_password")

    def fill(self, **values):
        self.fill_fields({name: value for name, value in values.items() if name in self.FIELDS})
        return self

    def register(self, **values):
        """Fill the form and press the submit button."""
        self.fill(**values)
        self.submit()
        return self


class TeacherRegisterPage(RegisterPage):
    path = "/teacher/register"
    FIELDS = RegisterPage.FIELDS + ("department",)
