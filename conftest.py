"""Root conftest: CLI options, execution-group wiring, and session fixtures.

What this provides
------------------
* ``--group <name>``     select an execution group from execution-groups.yaml
                         (sets the marker expression and parallel/serial mode).
* ``--run-disruptive``   also run tests marked ``@disruptive`` (opt-in).
* auto layer markers     tests under tests/<layer>/ get the matching marker
                         (api/contract/db/e2e) automatically - no per-test tags.
* session fixtures       ``settings``, ``stack`` (brings the app up fresh),
                         ``api``, ``db``; plus ``app_page`` (function scope) and
                         Playwright context defaults for the Polish UI.

Resource fixtures that create domain entities use ``yield`` + teardown so they
always clean up, independent of the test outcome. See tests/conftest.py and the
``*_steps`` modules for the per-layer pieces.
"""

from collections.abc import Iterator

import pytest

from alma_spei_tests.api import ApiClient
from alma_spei_tests.config import Settings, load_settings
from alma_spei_tests.db import DbClient
from alma_spei_tests.orchestration import Stack
from alma_spei_tests.plugin import resolve_group

# Layer directory -> marker name, applied automatically during collection.
_LAYER_MARKERS = {"api": "api", "contract": "contract", "db": "db", "e2e": "e2e"}


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup("alma-spei", "Alma Spei test suite")
    group.addoption(
        "--group",
        action="store",
        dest="alma_group",
        default=None,
        metavar="NAME",
        help="Run an execution group defined in execution-groups.yaml.",
    )
    group.addoption(
        "--run-disruptive",
        action="store_true",
        dest="run_disruptive",
        default=False,
        help="Also run tests marked @disruptive (restarts/disrupts the stack).",
    )


# ---------------------------------------------------------------------------
# Execution-group resolution (runs before xdist configures, via tryfirst)
# ---------------------------------------------------------------------------
@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config):
    config._alma_run_disruptive = bool(config.getoption("run_disruptive"))  # type: ignore[attr-defined]

    name = config.getoption("alma_group")
    if not name:
        return

    spec = resolve_group(name)

    # Marker expression: AND with anything the user already passed via -m.
    existing = config.option.markexpr
    config.option.markexpr = f"({existing}) and ({spec.markers})" if existing else spec.markers

    # Groups that target disruptive tests enable the opt-in automatically.
    if spec.run_disruptive:
        config._alma_run_disruptive = True  # type: ignore[attr-defined]

    # Parallelism via xdist. Only set when the user did not pass -n explicitly.
    if hasattr(config.option, "numprocesses"):
        if config.option.numprocesses in (None, 0):
            if spec.parallel:
                config.option.numprocesses = "auto"
                config.option.dist = "loadgroup"
            else:
                config.option.numprocesses = 0
                config.option.dist = "no"


# ---------------------------------------------------------------------------
# Collection: auto layer markers + disruptive opt-in gate
# ---------------------------------------------------------------------------
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    run_disruptive = getattr(config, "_alma_run_disruptive", False)
    skip_disruptive = pytest.mark.skip(
        reason="disruptive test; pass --run-disruptive or run `--group disruptive`"
    )

    for item in items:
        path = str(item.fspath).replace("\\", "/")
        for layer, marker in _LAYER_MARKERS.items():
            if f"/tests/{layer}/" in path:
                item.add_marker(getattr(pytest.mark, marker))
                break

        if item.get_closest_marker("disruptive") and not run_disruptive:
            item.add_marker(skip_disruptive)


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="session")
def stack(settings: Settings) -> Iterator[Stack]:
    """Bring the whole app up fresh for the session, and tear it down.

    With ALMA_NO_ORCHESTRATION=1 this only waits for an already-running app.
    """
    s = Stack(settings)
    s.up()
    try:
        yield s
    finally:
        s.down()


@pytest.fixture(scope="session")
def base_url(settings: Settings, stack: Stack) -> str:  # noqa: ARG001 - stack ensures app is up
    return settings.base_url


@pytest.fixture(scope="session")
def api(base_url: str, settings: Settings) -> Iterator[ApiClient]:
    client = ApiClient(base_url, timeout=settings.http_timeout_s)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def db(settings: Settings, stack: Stack) -> Iterator[DbClient]:  # noqa: ARG001 - stack ensures DB is up
    client = DbClient(settings)
    client.connect()
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Playwright context defaults (Polish locale, correct base URL)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, base_url: str) -> dict:
    return {**browser_context_args, "base_url": base_url, "locale": "pl-PL"}
