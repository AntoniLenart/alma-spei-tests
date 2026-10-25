"""The ``@step`` decorator used by all reusable step functions.

It logs the step title and, when allure-pytest is available, records the call
as an Allure step (so steps appear as a structured, collapsible tree in the
report with attachments on failure). The title may reference the wrapped
function's arguments with ``{name}`` placeholders::

    @step("Send GET {path}")
    def get(api, path):
        return api.get(path)

Allure is imported lazily and optionally, so steps still work (and still log)
when running without the Allure plugin installed.
"""

import functools
import inspect
from collections.abc import Callable
from typing import TypeVar

from alma_spei_tests.logging_setup import get_logger

try:  # optional dependency at runtime
    import allure

    _HAS_ALLURE = True
except ImportError:  # pragma: no cover
    allure = None  # type: ignore[assignment]
    _HAS_ALLURE = False

log = get_logger("step")

F = TypeVar("F", bound=Callable)


def _render_title(template: str, func: Callable, args: tuple, kwargs: dict) -> str:
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return template.format(**bound.arguments)
    except (KeyError, IndexError, TypeError, ValueError):
        return template


def step(title: str) -> Callable[[F], F]:
    """Mark a function as a named, reportable test step."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            rendered = _render_title(title, func, args, kwargs)
            log.info("STEP: %s", rendered)
            if _HAS_ALLURE:
                with allure.step(rendered):
                    return func(*args, **kwargs)
            return func(*args, **kwargs)

        wrapper.__step_title__ = title  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
