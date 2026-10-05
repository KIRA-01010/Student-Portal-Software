"""Teacher area: student records list / search, add, edit, view and delete."""

from typing import Dict, List

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base_page import LoggedInPage, normalise, old_page_gone

RECORD_FORM_FIELDS = (
    "registration_number",
    "first_name",
    "last_name",
    "department",
    "current_semester",
)


class StudentsListPage(LoggedInPage):
    """/teacher/students - the record table plus its search box."""

    path = "/teacher/students"

    SEARCH_INPUT = (By.CSS_SELECTOR, "main input[name='q']")
    SEARCH_BUTTON = (By.CSS_SELECTOR, "main form[method='get'] button[type='submit']")
    ROWS = (By.CSS_SELECTOR, "main table tbody tr")
    SUMMARY = (By.CSS_SELECTOR, "main h1 + p")          # "3 records matching ..."
    EMPTY_STATE = (By.CSS_SELECTOR, "main .text-center p")
    ADD_STUDENT = (By.CSS_SELECTOR, "main a[href$='/teacher/students/new']")

    # --------------------------------------------------------------- search
    def search(self, term: str) -> "StudentsListPage":
        """Type `term` in the search box and submit (a GET form => full reload)."""
        self.type_into(self.SEARCH_INPUT, term)
        old_input = self.find(self.SEARCH_INPUT)
        self.click(self.SEARCH_BUTTON)
        self.wait.until(old_page_gone(old_input))      # the page has reloaded
        self.find(self.SEARCH_INPUT)
        return self

    # --------------------------------------------------------------- reading
    def rows(self) -> List[Dict[str, str]]:
        table = []
        for row in self.driver.find_elements(*self.ROWS):
            cells = [normalise(td.get_attribute("textContent")) for td in row.find_elements(By.TAG_NAME, "td")]
            if len(cells) >= 5:
                table.append(
                    {
                        "registration_number": cells[0],
                        "name": cells[1],
                        "department": cells[2],
                        "semester": cells[3],
                        "cgpa": cells[4],
                    }
                )
        return table

    def registration_numbers(self) -> List[str]:
        return [row["registration_number"] for row in self.rows()]

    def has_record(self, registration_number: str) -> bool:
        return registration_number in self.registration_numbers()

    def summary(self) -> str:
        """e.g. '3 records matching “abc”'."""
        return self.text_of(self.SUMMARY)

    def empty_message(self) -> str:
        return self.text_of(self.EMPTY_STATE)

    # --------------------------------------------------------------- actions
    def click_add_student(self) -> "StudentFormPage":
        self.click(self.ADD_STUDENT)
        page = StudentFormPage(self.driver, self.base_url)
        page.wait_for_path("/teacher/students/new")
        return page

    def _row_action(self, registration_number: str, title: str):
        xpath = (
            f"//main//table//tr[td[1][normalize-space()='{registration_number}']]"
            f"//a[@title='{title}']"
        )
        element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        self.scroll_to(element)  # long lists: avoid clicking mid smooth-scroll
        return element

    def open_record(self, registration_number: str) -> "StudentDetailPage":
        self._row_action(registration_number, "View").click()
        page = StudentDetailPage(self.driver, self.base_url)
        page.wait_until_loaded()
        return page

    def edit_record(self, registration_number: str) -> "StudentFormPage":
        self._row_action(registration_number, "Edit").click()
        page = StudentFormPage(self.driver, self.base_url)
        page.wait_for_path_matching(r"^/teacher/students/\d+/edit$")
        return page

    def delete_record(self, registration_number: str) -> "DeleteConfirmPage":
        self._row_action(registration_number, "Delete").click()
        page = DeleteConfirmPage(self.driver, self.base_url)
        page.wait_for_path_matching(r"^/teacher/students/\d+/delete$")
        return page


class StudentFormPage(LoggedInPage):
    """Add-student form (default) - also the Edit form once opened from the list."""

    path = "/teacher/students/new"

    HEADING = (By.CSS_SELECTOR, "main h1")
    LOCKED_REGISTRATION_NUMBER = (By.CSS_SELECTOR, "main form input[disabled]")

    def fill(self, **values) -> "StudentFormPage":
        self.fill_fields({k: v for k, v in values.items() if k in RECORD_FORM_FIELDS})
        return self

    def save(self) -> "StudentFormPage":
        self.submit()
        return self

    def add(self, **record) -> "StudentDetailPage":
        """Fill and submit the form, then wait for the new record's page."""
        self.fill(**record).save()
        detail = StudentDetailPage(self.driver, self.base_url)
        detail.wait_until_loaded()
        return detail

    def heading(self) -> str:
        return self.text_of(self.HEADING)

    def values(self) -> Dict[str, str]:
        """Current values of the editable fields."""
        return {
            name: self.field_value(name)
            for name in ("first_name", "last_name", "department", "current_semester")
        }

    def registration_number_is_locked(self) -> bool:
        """Edit mode shows the registration number as a disabled input."""
        fields = self.driver.find_elements(*self.LOCKED_REGISTRATION_NUMBER)
        return bool(fields) and not fields[0].is_enabled()

    def locked_registration_number(self) -> str:
        return self.find(self.LOCKED_REGISTRATION_NUMBER).get_attribute("value")


class StudentDetailPage(LoggedInPage):
    """/teacher/students/<id> - one record's summary."""

    HEADING = (By.CSS_SELECTOR, "main h1")
    META = (By.CSS_SELECTOR, "main h1 + p")     # "REG-123 · Computer Science"
    SEMESTER = (
        By.XPATH,
        "//main//h2[normalize-space()='Current semester']/following-sibling::p[1]",
    )

    def wait_until_loaded(self) -> int:
        """Wait for /teacher/students/<id>; returns the record id."""
        match = self.wait_for_path_matching(r"^/teacher/students/(\d+)$")
        return int(match.group(1))

    def name(self) -> str:
        return self.text_of(self.HEADING)

    def registration_number(self) -> str:
        return self.text_of(self.META).split("\u00b7")[0].strip()

    def department(self) -> str:
        return self.text_of(self.META).split("\u00b7")[1].strip()

    def current_semester(self) -> str:
        return self.text_of(self.SEMESTER)


class DeleteConfirmPage(LoggedInPage):
    """/teacher/students/<id>/delete - 'Are you sure?' step."""

    HEADING = (By.CSS_SELECTOR, "main h1")
    BODY = (By.CSS_SELECTOR, "main .card-body")
    CONFIRM = (By.CSS_SELECTOR, "main form button.btn-danger")
    CANCEL = (By.CSS_SELECTOR, "main a.btn-outline-secondary")

    def heading(self) -> str:
        return self.text_of(self.HEADING)

    def body_text(self) -> str:
        return self.text_of(self.BODY)

    def confirm_delete(self) -> StudentsListPage:
        self.click(self.CONFIRM)
        page = StudentsListPage(self.driver, self.base_url)
        page.wait_for_path("/teacher/students")
        return page

    def cancel(self) -> StudentDetailPage:
        self.click(self.CANCEL)
        page = StudentDetailPage(self.driver, self.base_url)
        page.wait_until_loaded()
        return page
