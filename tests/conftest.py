"""Fixtures shared across the test layers.

``app_page`` gives every browser test a fresh page object for the shell.
"""

import pytest
from playwright.sync_api import Page

from alma_spei_tests.pages import AppPage


# --- browser ------------------------------------------------------------------
@pytest.fixture
def app_page(page: Page) -> AppPage:
    """A fresh AppPage per test (pytest-playwright provides ``page``)."""
    return AppPage(page)
