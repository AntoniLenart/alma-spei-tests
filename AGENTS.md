# Instructions for coding agents — Alma Spei test suite

## Mission

Provide software quality assurance (SQA) for the **Alma Spei** donor management
system (the application repo, expected at `../alma-spei`). This repository holds
an automated test suite built with **pytest** and **Playwright**, plus the
orchestration that runs the real app for end-to-end verification.

**Use English** for code, identifiers, comments and documentation. The
application UI is Polish, so tests assert against exact **Polish** user-facing
strings - keep those strings as named constants, never scatter literals.

## Non-negotiable constraints

1. **Synthetic data only.** Never put real donor or personal data in fixtures,
   factories, commits, logs, screenshots, traces or prompts. Use
   `alma_spei_tests.data` (Polish-locale Faker). This mirrors the app's own
   GDPR/synthetic-data rule.
2. **Test, don't fix.** This repo tests the app; it does not change app code. A
   failing test that reflects a real app bug is a correct outcome - report it,
   do not weaken the test to make it pass.
3. **Respect the app's decision gates.** Requirements in `../alma-spei/docs` are
   split into CONFIRMED / PROPOSED / OPEN. Only write tests against implemented,
   confirmed behavior; mark the rest as pending app implementation.

## Repository conventions

- **OOP tests.** Test classes derive from a base in `alma_spei_tests.testbase`.
  Methods are named `test_<descriptive_snake_case>`.
- **Numbered scenario steps as a block at the top.** List every step as a
  numbered comment (`# 1.`, `# 2.`, ...) at the top of the test body, then the
  code below. The last numbered comment is the verification.
- **Reusable steps.** Shared actions are `@step("...")`-decorated functions in
  `src/alma_spei_tests/steps/*_steps.py`. Tests call them.
- **assertpy via named helpers, not inline chains.** Common checks go through a
  helper in `alma_spei_tests.assertions` (e.g. `assert_health_ok(response)`).
  Do not write bare `assert_that(...).is_equal_to(...)` chains in tests for
  recurring checks. A helper used by only one file may live at the **end** of
  that file. Every assertion uses `.described_as("... should ...")` with an
  expectation-style message. The equality method is `is_equal_to`.
- **Soft assertions for multiple checks.** When a test or helper makes more than
  one assertion, wrap them in `with soft_assertions():` so all failures report.
- **No magic literals.** Content types, status strings, payloads, expected
  versions, Polish UI strings, etc. are named constants/enums
  (`alma_spei_tests.constants`, or `ShellMessages` on the page object).
- **Type hints everywhere, except `-> None`.** Annotate parameters and non-None
  return types. Do not write `-> None`. Do not add
  `from __future__ import annotations`.
- **Utilities outside test files.** Clients, page objects, steps, factories,
  constants, assertions and contracts live in the `alma_spei_tests` package.
  Extract shared code; stay DRY.
- **Fixtures with correct scope.** Session-scoped stack/clients; function-scoped
  page objects and per-test resources. Resource fixtures create in setup and
  tear down after `yield` so **cleanup always runs, independent of the test**.
- **Smaller conftests are fine.** Put layer-specific fixtures in
  `tests/<layer>/conftest.py`; keep cross-cutting ones at the root.
- **Layer markers are automatic** by directory (`api`/`contract`/`db`/`e2e`);
  add `smoke`/`slow` explicitly.
- **Page objects never assert.** They expose locators, queries and waits.

## Execution model

- **uv** manages the environment (Python 3.12). `uv sync`, then
  `uv run playwright install` once.
- **Orchestration is full and always-fresh**: the session `stack` fixture brings
  up Postgres (Docker), runs migrations, builds the frontend and starts the
  backend on loopback, then tears it all down. It isolates itself from a dev
  stack via a dedicated compose project and its own ports. Set
  `ALMA_NO_ORCHESTRATION=1` to test an already-running app at `BASE_URL`.
- **Parallel execution** via pytest-xdist. **Execution groups** are declared in
  `execution-groups.yaml` and run with `pytest --group <name>`.
- **Disruptive tests** (`@disruptive`) are opt-in (`--run-disruptive` or
  `--group disruptive`) and run serially/isolated.

## Agents in this repo

Defined under `.claude/agents/`:

- **test-author** - writes tests following these conventions.
- **test-runner-triage** - runs the suite and triages failures.
- **page-object-maintainer** - keeps Playwright selectors centralized and current.
- **requirements-coverage-mapper** - maps tests to `../alma-spei/docs` criteria.

## Before writing code

Read this file, `README.md`, and the relevant `../alma-spei/docs/*`. Prefer
extending the support package over duplicating logic in tests. When adding a new
kind of selection, edit `execution-groups.yaml` rather than hard-coding it.
