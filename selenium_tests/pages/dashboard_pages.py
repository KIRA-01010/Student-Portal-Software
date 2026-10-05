"""Landing pages shown right after signing in."""

from selenium.webdriver.common.by import By

from .base_page import LoggedInPage


class DashboardPage(LoggedInPage):
    """Student dashboard."""

    path = "/dashboard"
    HEADING = (By.CSS_SELECTOR, "main h1")

    def heading(self) -> str:
        return self.text_of(self.HEADING)


class TeacherDashboardPage(DashboardPage):
    path = "/teacher/dashboard"
