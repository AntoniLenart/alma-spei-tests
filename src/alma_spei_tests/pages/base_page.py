"""Base page object.

Page objects own locators and page interactions; they never assert. Tests pull
values/locators from page objects and do the assertions (with assertpy). This
keeps selectors in one place (DRY) and assertions in the tests (readable).
"""

from playwright.sync_api import Page


class BasePage:
    #: Subclasses set the path this page lives at (relative to base_url).
    path: str = "/"

    def __init__(self, page: Page):
        self.page = page

    def open(self) -> "BasePage":
        """Navigate to this page's path and return self for chaining."""
        self.page.goto(self.path)
        return self

    def title(self) -> str:
        return self.page.title()
