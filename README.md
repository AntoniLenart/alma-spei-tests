# Alma Spei — SQA test suite

Automated quality assurance for the [Alma Spei](https://github.com/zapjur/alma-spei)
donor management system, built with **pytest** and **Playwright**. The suite
covers four layers — API/HTTP, response contracts, direct database checks, and
end-to-end browser tests of the Polish UI — and can bring the whole application
stack up fresh to test against.

> Test data is **always synthetic** (Polish-locale Faker). Never introduce real
> personal data — see [`AGENTS.md`](AGENTS.md).

## Requirements

- **Python 3.12** and **[uv](https://docs.astral.sh/uv/)**.
- For orchestrated runs (the default), the same toolchain the app needs:
  **JDK 25**, **Clojure CLI**, **Node 24** + npm, **Babashka**, and **Docker**
  with Compose v2, all runnable from your PATH.
- The application repo checked out at `../alma-spei` (or set `ALMA_APP_REPO`).
- To render Allure reports: the **Allure CLI** (needs Java).

## Setup

```sh
uv sync                     # create the venv and install dependencies
uv run playwright install   # download the Playwright browsers (first time only)
```

## Running the tests

The session `stack` fixture brings the app up **fresh** (Docker Postgres →
migrations → QA admin provisioning → frontend release build → backend on
loopback) and tears it down afterwards. It isolates itself from any dev stack
with a dedicated Docker Compose project and its own ports, so it won't clobber
your development database.

The QA administrator (`qa.admin`) is provisioned without a console and its
one-time temporary password is rotated by the session `api` fixture to a known
synthetic password (`ALMA_QA_ADMIN_*` overrides; see `config.py`).

Orchestrated runs are **serial**: one stack owns fixed ports and one database,
so `-n` is refused unless `ALMA_NO_ORCHESTRATION=1`. Logins are throttled per
client address (30 per 15 min), so e2e tests borrow an API session instead of
logging in through the form wherever login itself is not under test.

```sh
# Everything except disruptive tests (the default regression run)
uv run pytest --group regression

# A single layer / group (see execution-groups.yaml)
uv run pytest --group api
uv run pytest --group contract
uv run pytest --group db
uv run pytest --group e2e
uv run pytest --group smoke

# Disruptive tests (app restarts): opt-in and serial
uv run pytest --group disruptive

# Ad hoc selection still works
uv run pytest -m "api and smoke" -k health
```

Execution groups live in [`execution-groups.yaml`](execution-groups.yaml); each
group is a marker expression plus a parallel/serial flag. Adding a group is a
YAML edit, not code. All groups are currently serial (see above); `parallel:
true` runs a group under pytest-xdist (`-n auto`, `--dist loadgroup`) and is only
valid against an already-running app.

### Testing an already-running app

To skip orchestration (e.g. you started the app yourself with `bb` in the app
repo), point the suite at it. An administrator with the `ALMA_QA_ADMIN_USERNAME`
/ `ALMA_QA_ADMIN_PASSWORD` credentials (password already rotated) must exist:

```sh
ALMA_NO_ORCHESTRATION=1 BASE_URL=http://127.0.0.1:3000 uv run pytest --group smoke
```

## Static checks

These need no app, Docker or browsers, and CI runs them on every pull request
(`.github/workflows/checks.yml`):

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy                          # config in pyproject.toml
uv run pytest --collect-only -q      # every test imports and collects
```

## Reports and artifacts

All under `reports/`:

- **Allure**: results in `reports/allure-results` →
  `allure serve reports/allure-results`.
- **HTML**: `reports/report.html` (self-contained).
- **Playwright** traces/videos/screenshots on failure:
  `reports/playwright-artifacts/`.
- **Backend log** from the orchestrated stack: `reports/stack/backend.log`.

## Layout

```text
alma-spei-tests/
├── conftest.py                 # CLI options, --group wiring, session fixtures
├── execution-groups.yaml       # named, data-driven test groups
├── pyproject.toml              # uv deps + pytest/ruff/mypy config
├── AGENTS.md                   # conventions for coding agents
├── .github/                    # PR checks workflow + pull request template
├── .claude/agents/             # test-author, triage, page-object, coverage
├── src/alma_spei_tests/        # support package (no tests here)
│   ├── config.py               # env-derived Settings
│   ├── orchestration/          # toolchain preflight + Stack (up/down/restart)
│   │                           #   + provision_admin.clj (non-interactive admin)
│   ├── http/                   # AuthSession: cookie jar, Origin, CSRF headers
│   ├── clients/                # Health/Auth/Accounts/Donors clients + AlmaSpeiApi facade
│   ├── db/                     # psycopg client + DbQueries (named queries)
│   ├── contracts/              # Python mirrors of the app's Malli contracts (mini schema DSL)
│   ├── pages/                  # Playwright page objects (locators, no asserts)
│   ├── steps/                  # @step-decorated reusable steps
│   ├── data/                   # synthetic (Faker pl_PL) factories
│   ├── testbase/               # OOP base test classes
│   └── plugin/                 # execution-group loader
└── tests/
    ├── conftest.py             # donor/account resource fixtures, staff_api, signed_in_page
    ├── api/                    # health, errors, sessions/CSRF, passwords, accounts, donors
    ├── contract/               # health, auth and donor responses vs schema
    ├── db/                     # migration, credential/session/audit, donor persistence
    └── e2e/                    # shell, login, donor list + card, backend-restart (disruptive)
```

## Conventions (summary)

- **OOP**: tests are classes extending `alma_spei_tests.testbase` bases;
  methods `test_<descriptive>`.
- **Numbered steps as a block at the top** of each test body, code below; the
  last numbered comment is the verification.
- **Reusable steps** as `@step("...")` functions in `steps/*_steps.py`.
- **Assertions via helpers**: common checks call `alma_spei_tests.assertions`
  (e.g. `assert_health_ok(response)`); file-local helpers go at the end of the
  file. assertpy only, always `.described_as("... should ...")`, equality via
  `is_equal_to`. Multiple assertions use `with soft_assertions():`.
- **No magic literals**: content types, statuses and payloads live in
  `alma_spei_tests.constants`; Polish UI strings in page-object constants.
- **Type hints everywhere except `-> None`**; no `from __future__ import annotations`.
- **Fixtures** with explicit scope; resource fixtures clean up after `yield`,
  independent of the test outcome.
- **Utilities live in the package**, not in test files — keep it DRY.

See [`AGENTS.md`](AGENTS.md) for the full rules.
