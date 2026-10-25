"""Support package for the Alma Spei SQA test suite.

Everything that is not a test lives here: configuration, API/DB clients,
Playwright page objects, reusable steps, synthetic data factories, base test
classes and the stack orchestration used by the session fixtures.

Tests import from this package so that test files stay thin and DRY.
"""

__all__ = ["config"]
