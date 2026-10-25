"""Base classes for test classes.

Tests are written OOP-style: each test file groups related scenarios into a
class deriving from one of these bases. The hierarchy documents each test's
layer and is the home for any future layer-specific shared behaviour.

Shared *fixtures* live in conftest.py; shared *assertion helpers* live in
``alma_spei_tests.assertions``; file-local helpers go at the end of the test
file that needs them.
"""


class BaseTest:
    """Root base for every test class."""


class BaseApiTest(BaseTest):
    """HTTP/API layer tests."""


class BaseContractTest(BaseApiTest):
    """Response-vs-schema contract tests."""


class BaseDbTest(BaseTest):
    """Direct PostgreSQL assertion tests."""


class BaseE2ETest(BaseTest):
    """Playwright browser tests of the Polish UI."""
