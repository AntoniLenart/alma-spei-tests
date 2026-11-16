# Alma Spei — SQA test suite

[![Checks](https://github.com/AntoniLenart/alma-spei-tests/actions/workflows/checks.yml/badge.svg)](https://github.com/AntoniLenart/alma-spei-tests/actions/workflows/checks.yml)
[![Regression](https://github.com/AntoniLenart/alma-spei-tests/actions/workflows/regression.yml/badge.svg)](https://github.com/AntoniLenart/alma-spei-tests/actions/workflows/regression.yml)
[Latest regression report (Allure)](https://antonilenart.github.io/alma-spei-tests/)

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

The backend runs in the app's **synthetic import mode** (`ALMA_SYNTHETIC_IMPORTS`),
the only way to commit an import before a real backup provider exists: its
receipts are labelled `synthetic-test-v1` and create no real backup. Set
`ALMA_TEST_SYNTHETIC_IMPORTS=0` to start it without; the commit and undo tests
then fail with `backup-unavailable`, as the app intends.

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

The synthetic-data tests (`tests/db/test_synthetic_data.py`) run the app's
`seed-demo` loader and skip without orchestration, so they never write demo
rows into a database you started yourself. The commit and undo tests need the
app started with `ALMA_SYNTHETIC_IMPORTS=true`, and they write committed
(and undone) synthetic imports into its database.

### Running on Windows

The suite and the app run on Windows (the app's Windows fixes - private files
under Windows ACLs and LF-only shell scripts via `.gitattributes` - are on its
`main`). A few machine-level points remain:

- **JDK 25 for the Clojure CLI.** Set `JAVA_HOME` to it and put its `bin` first
  on `PATH`, so an older `java` (e.g. a Java 8 install) is never picked up.
- **Ports.** Hyper-V may reserve the default test DB port (55432); check
  `netsh interface ipv4 show excludedportrange protocol=tcp` and set
  `ALMA_TEST_DB_PORT` (and `ALMA_TEST_HTTP_PORT`) to free ports.
- **Backend left running.** Teardown stops the `clojure` launcher, but its
  `java` child keeps the HTTP port; stop it before the next run, or use another
  `ALMA_TEST_HTTP_PORT`.

Older app checkouts (before those fixes) still need the earlier workarounds:
create `.secrets/` by hand with `ALMA_BB_CMD=true`, convert
`infra/postgres/*.sh` to LF, and expect uploads to fail with HTTP 500.

## Static checks

These need no app, Docker or browsers, and CI runs them on every pull request
(`.github/workflows/checks.yml`):

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy                          # config in pyproject.toml
uv run pytest --collect-only -q      # every test imports and collects
```

## Full regression in GitHub Actions

[`.github/workflows/regression.yml`](.github/workflows/regression.yml) runs the
whole app-backed suite against the dev repo and publishes the
[Allure report](https://antonilenart.github.io/alma-spei-tests/) to GitHub Pages:

- **After every merge to dev `main`.** A light job checks dev `main` every 15
  minutes and starts a run once per new commit (the tested commit is recorded
  next to the report as `last-dev-sha`).
- **By hand** (*Actions → Regression → Run workflow*) against any dev branch,
  tag or commit, e.g. a dev branch before it is merged.
- **From a pull request** that changes the workflow (validation, nothing is
  published).

Each run checks out that dev commit, installs the toolchain at the versions the
dev CI pins (Temurin JDK, Clojure CLI, Babashka, Node), lets the suite bring up a
fresh stack (synthetic import mode), runs `--group regression` and then
`--group disruptive`, and builds one Allure report with the history of earlier
runs. The run summary lists the counts and failing tests; the HTML reports, the
backend log and Playwright artifacts are kept as run artifacts for 14 days. A run
with failing tests is marked failed, but its report is still published.

GitHub pauses scheduled workflows in a public repository after 60 days without
activity; re-enable it in the Actions tab if that happens.

## Branches and pull requests

- Every dev branch with testable work gets a test branch **of the same name**
  (`trello/<id>-<slug>`, `project-foundation`, …), stacked the same way the dev
  branches are. Test-only changes use a descriptive branch name instead.
- Test branches are written against the dev branch's real code, never against
  planned behaviour, and run with `ALMA_APP_REPO` pointing at a checkout of the
  matching dev branch.
- Open each pull request into `main` with the template in `.github/`. Merge it
  with a merge commit (not squash) once its dev branch is merged to dev `main`,
  stacked branches in order, and with CI green. Delete the branch after the
  merge.

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
│   ├── orchestration/          # toolchain preflight + Stack (up/down/restart/seed-demo)
│   │                           #   + provision_admin.clj (non-interactive admin)
│   ├── http/                   # AuthSession: cookie jar, Origin, CSRF headers
│   ├── clients/                # Health/Auth/Accounts/Donors/Imports clients + AlmaSpeiApi facade
│   ├── db/                     # psycopg client + DbQueries (named queries,
│   │                           #   constraint probes that always roll back)
│   ├── contracts/              # Python mirrors of the app's Malli contracts (mini schema DSL)
│   ├── pages/                  # Playwright page objects (locators, no asserts)
│   ├── steps/                  # @step-decorated reusable steps (review and execution
│   │                           #   workflows read the versions they must send first)
│   ├── data/                   # synthetic (Faker pl_PL) factories, bank statements,
│   │                           #   review decisions
│   ├── testbase/               # OOP base test classes
│   └── plugin/                 # execution-group loader
└── tests/
    ├── conftest.py             # donor/account fixtures, staff_api, admin_id, signed_in_page,
    │                           #   staged/decided/committed imports
    ├── api/                    # health, errors, sessions/CSRF, passwords, accounts, donors,
    │                           #   bank upload + rows, review queue, decisions, previews,
    │                           #   commit, undo and re-import
    ├── contract/               # health, auth, donor, import, review, decision and
    │                           #   execution responses vs schema
    ├── db/                     # migration, credential/session/audit, donor persistence,
    │                           #   donor + import schema constraints and grants,
    │                           #   synthetic demo data (seed-demo), staging, review
    │                           #   decisions, commit provenance and undo compensation
    └── e2e/                    # shell, login, donor list + card, upload, review queue,
                                #   decision editor + preview, confirmation, history,
                                #   undo + re-import, backend-restart (disruptive)
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
