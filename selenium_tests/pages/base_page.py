"""Behaviour shared by every page object (Page Object Model).

Rules the page objects follow:
  * explicit waits only - no time.sleep() and no implicit waits;
  * locators live on the page class, tests never contain a CSS selector;
  * message text is read with `textContent`, so it works whether or not the
    Bootstrap CSS from the CDN managed to load.
"""

import re
from typing import Dict, List
from urllib.parse import urlparse

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT = 10


# What Chrome's DevTools protocol says about an element id that belonged to a
# document that has since been replaced.
_GONE_NODE_MESSAGES = (
    "does not belong to the document",
    "Could not find node with given id",
    "No node with given id found",
)


def old_page_gone(old_element):
    """Expected condition: True once `old_element` belongs to a page that has gone.

    Use it right after an action that reloads the page, with an element found
    *before* that action. Selenium's own `EC.staleness_of` only understands the
    "stale element reference" error, but Chrome 153 sometimes answers a probe on
    a node from the just-replaced document with a raw inspector error instead
    ("Node with given id does not belong to the document"). That crashed the
    wait even though the page had reloaded correctly. Any other WebDriver error
    is still raised.
    """

    def check(driver):
        try:
            old_element.is_enabled()
            return False
        except StaleElementReferenceException:
            return True
        except WebDriverException as error:
            if any(fragment in (error.msg or "") for fragment in _GONE_NODE_MESSAGES):
                return True
            raise

    return check


def normalise(text: str) -> str:
    """Collapse runs of whitespace so comparisons ignore template indentation."""
    return " ".join((text or "").split())


class BasePage:
    path = "/"

    # Flash messages and in-form alerts all render inside <main>.
    ALERTS = (By.CSS_SELECTOR, "main .alert")
    # Alert rendered *inside* the form card (login / register / record forms).
    FORM_ALERT = (By.CSS_SELECTOR, "main .card .alert")
    FORM = (By.CSS_SELECTOR, "main form.needs-validation")
    SUBMIT = (By.CSS_SELECTOR, "main form.needs-validation button[type='submit']")

    # Navbar: the account dropdown only exists for a signed-in user.
    ACCOUNT_MENU = (By.CSS_SELECTOR, "nav .dropdown-toggle")

    def __init__(self, driver, base_url: str, timeout: int = DEFAULT_TIMEOUT):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, timeout)

    # ------------------------------------------------------------ navigation
    @property
    def url(self) -> str:
        return f"{self.base_url}{self.path}"

    def open(self):
        self.driver.get(self.url)
        return self

    @property
    def current_path(self) -> str:
        return urlparse(self.driver.current_url).path

    def wait_for_path(self, path: str) -> None:
        try:
            self.wait.until(lambda d: urlparse(d.current_url).path == path)
        except TimeoutException:
            raise AssertionError(
                f"Expected the browser to be on {path!r} but it is on {self.current_path!r}"
            ) from None

    def wait_for_path_matching(self, pattern: str) -> "re.Match":
        """Wait until the URL path matches a regex; returns the match."""
        regex = re.compile(pattern)
        try:
            self.wait.until(lambda d: regex.match(urlparse(d.current_url).path))
        except TimeoutException:
            raise AssertionError(
                f"Expected a path matching {pattern!r} but the browser is on {self.current_path!r}"
            ) from None
        return regex.match(self.current_path)

    # -------------------------------------------------------------- elements
    def find(self, locator):
        return self.wait.until(EC.presence_of_element_located(locator))

    def visible(self, locator):
        return self.wait.until(EC.visibility_of_element_located(locator))

    def scroll_to(self, element) -> None:
        """Bring `element` into the middle of the window *instantly*.

        Bootstrap 5 sets `scroll-behavior: smooth` on the page. WebDriver scrolls
        an element into view and clicks straight away, so on a window shorter
        than the form the click used to fire while the animated scroll was still
        running and Chrome raised ElementClickInterceptedException ("not
        clickable at point ..." with the point below the visible area).
        Centring (rather than aligning to an edge) also keeps the element out
        from under the sticky navbar.
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'});",
            element,
        )

    def click(self, locator) -> None:
        element = self.wait.until(EC.element_to_be_clickable(locator))
        self.scroll_to(element)
        element.click()

    def type_into(self, locator, text: str) -> None:
        element = self.visible(locator)
        element.clear()
        if text:
            element.send_keys(text)

    def text_of(self, locator) -> str:
        return normalise(self.find(locator).get_attribute("textContent"))

    # -------------------------------------------------------------- messages
    def messages(self) -> List[str]:
        """Text of every alert currently on the page (flash + in-form)."""
        return [
            normalise(el.get_attribute("textContent"))
            for el in self.driver.find_elements(*self.ALERTS)
        ]

    def wait_for_message(self, fragment: str) -> None:
        wanted = fragment.lower()
        try:
            self.wait.until(lambda d: any(wanted in m.lower() for m in self.messages()))
        except TimeoutException:
            raise AssertionError(
                f"No message containing {fragment!r}. Messages on the page: {self.messages()}"
            ) from None

    def form_alert(self) -> str:
        """The alert shown inside the form card (server-level form error)."""
        return normalise(self.visible(self.FORM_ALERT).get_attribute("textContent"))

    # ------------------------------------------------------------ navbar state
    def has_account_menu(self) -> bool:
        """True when the navbar shows the signed-in account dropdown."""
        return bool(self.driver.find_elements(*self.ACCOUNT_MENU))

    # ------------------------------------------------------------------ forms
    def fill_fields(self, values: Dict[str, str]) -> None:
        for name, value in values.items():
            self.type_into((By.ID, name), value)

    def submit(self) -> None:
        self.click(self.SUBMIT)

    def field_value(self, name: str) -> str:
        return self.find((By.ID, name)).get_attribute("value")

    def invalid_fields(self) -> List[str]:
        """Ids of the fields the *browser* currently considers invalid."""
        return self.driver.execute_script(
            "return Array.from(document.querySelectorAll('main form :invalid'))"
            ".map(function (e) { return e.id || e.name; });"
        )

    def form_was_validated(self) -> bool:
        """Bootstrap adds `was-validated` once client-side validation has run."""
        return "was-validated" in (self.find(self.FORM).get_attribute("class") or "")

    def field_has_server_error(self, name: str) -> bool:
        """True once the server has re-rendered the page with this field flagged.

        Polls, because right after a submit the browser may still be showing the
        old page for a moment. (Bootstrap's own client-side styling never adds
        `is-invalid`, so this only reports server-side errors.)
        """

        def flagged(driver):
            try:
                return "is-invalid" in (driver.find_element(By.ID, name).get_attribute("class") or "")
            except (NoSuchElementException, StaleElementReferenceException):
                return False

        try:
            self.wait.until(flagged)
            return True
        except TimeoutException:
            return False

    def field_message(self, name: str) -> str:
        """Text of the field's feedback element (server message when flagged)."""
        return normalise(self.find((By.ID, f"{name}-feedback")).get_attribute("textContent"))

    def bypass_client_validation(self) -> None:
        """Let an invalid form reach the server.

        The portal's JavaScript stops the submit when `form.checkValidity()` is
        false. Replacing that call lets a test prove the *server* re-validates
        everything and does not trust the browser.
        """
        self.driver.execute_script(
            "document.querySelector('main form.needs-validation').checkValidity ="
            " function () { return true; };"
        )


class LoggedInPage(BasePage):
    """A page showing the signed-in navbar (student or teacher)."""

    LOGOUT = (By.CSS_SELECTOR, "nav form[action$='logout'] button[type='submit']")

    def logout(self) -> None:
        """Open the account dropdown and press Logout."""
        self.click(self.ACCOUNT_MENU)
        try:
            WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable(self.LOGOUT)).click()
        except TimeoutException:
            # Bootstrap's dropdown JS did not open the menu (for example the
            # CDN was unreachable): press the button directly.
            button = self.find(self.LOGOUT)
            self.driver.execute_script("arguments[0].click();", button)
