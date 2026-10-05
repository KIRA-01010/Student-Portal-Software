"""Administrator student account and academic-record management page."""

from .base_page import LoggedInPage
from .students_pages import StudentDetailPage
from selenium.webdriver.common.by import By


class AdminStudentsPage(LoggedInPage):
    path = "/admin/students"

    def create(self, **values) -> StudentDetailPage:
        """Create a student through the current administrator workflow."""
        self.fill_fields(
            {
                name: values[name]
                for name in (
                    "registration_number",
                    "first_name",
                    "last_name",
                    "email",
                    "password",
                    "confirm_password",
                    "department",
                    "academic_year",
                )
                if name in values
            }
        )
        for name in ("season", "current_semester", "entry_type"):
            if name in values:
                self.driver.execute_script(
                    "document.getElementsByName(arguments[0])[0].value = arguments[1];",
                    name,
                    values[name],
                )
        form = self.find((By.CSS_SELECTOR, "main form[action$='/admin/students']"))
        self.driver.execute_script("arguments[0].requestSubmit();", form)
        self.wait_for_path("/admin/students")
        return self

    def create_record(self, record: dict) -> StudentDetailPage:
        """Create the account that owns the corresponding teacher record."""
        values = {
            "registration_number": record["registration_number"],
            "first_name": record["first_name"],
            "last_name": record["last_name"],
            "email": f"student.{record['registration_number']}@example.com",
            "password": "Passw0rd!123",
            "confirm_password": "Passw0rd!123",
            "department": record["department"],
            "season": "Fall",
            "academic_year": "2026",
            "current_semester": record["current_semester"],
            "entry_type": "Regular",
        }
        self.create(**values)
        return StudentDetailPage(self.driver, self.base_url)
