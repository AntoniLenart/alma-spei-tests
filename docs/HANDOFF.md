# Handoff — SQA rebuild against dev feature branches

Written for the next Claude Code session (and the maintainer). This captures the
plan, the research, and the exact next steps so work resumes without re-deriving
anything. Date: 2026-11-11.

## Goal

Rebuild the Alma Spei test suite to cover the dev app's real features, mirroring
the dev repo's branches 1:1 with stacked test branches, using properly
encapsulated clients. Then install the toolchain and get a green run.

## Repos & worktrees

- Dev app: `c:\STUDIA\mpt\alma-spei` (github.com/zapjur/alma-spei), on `main`.
- Tests:   `c:\STUDIA\mpt\alma-spei-tests` (github.com/AntoniLenart/alma-spei-tests), on `main`.
- Dev worktrees already created (paired, for reading/running each branch):
  - `c:\STUDIA\mpt\wt\dev\35` → branch `trello/35-bank-parser`
  - `c:\STUDIA\mpt\wt\dev\36` → branch `trello/36-import-upload`
  - `c:\STUDIA\mpt\wt\dev\37` → branch `trello/37-review-queue`
- Test worktrees: NOT yet created. Create them per branch when building each.

The three dev branches are **stacked**: 35 ⊂ 36 ⊂ 37. `main` already has auth +
donors + imports-foundation merged.

## Confirmed decisions (do not re-ask)

1. Shred scope: delete old example tests, KEEP the harness (orchestration,
   config, pyproject, conftest, execution-groups, agents). Rebuild clients +
   tests. (Old example tests + monolithic `api/client.py` already removed in the
   WIP commit that added this file.)
2. Branch mapping: mirror dev 1:1, STACKED. tests-`main` covers health+auth+
   donors; test branches `trello/35-bank-parser` ⊂ `trello/36-import-upload` ⊂
   `trello/37-review-queue` each add that ticket's import tests.
3. Worktrees: paired dev + test worktree per branch; the test config's
   `ALMA_APP_REPO` points at the paired dev worktree (`wt/dev/35` etc.).
4. Toolchain install: Scoop (user-space). Install uv, a modern JDK (temurin),
   Clojure CLI, Babashka. Current machine has only Java 8 + Node + Docker.
5. Co-authors on commits:
   - tests-`main`: NO co-author.
   - `trello/35-bank-parser`: `Co-Authored-By: Dewiant112 <pawel.piwowarczyk.eu@gmail.com>`
   - `trello/36-import-upload`: NO co-author.
   - `trello/37-review-queue`: `Co-Authored-By: Dewiant112 <pawel.piwowarczyk.eu@gmail.com>`
   - NEVER add a Claude/Anthropic co-author trailer (standing user rule).
6. Trello: no test tickets exist yet; create them later once the Trello MCP is
   connected (user sets that up interactively). Do not reference test-ticket
   numbers in branches/commits.

## App API surface (what to test)

On `main`:
- Health (no auth): `GET /api/health/live`, `GET /api/health/ready`.
- Auth (session cookie + CSRF):
  - `GET /api/auth/session` → `{user|null, csrf}` (sets `alma-csrf` cookie).
  - `POST /api/auth/login` `{username,password}` → sets `alma-session` cookie.
  - `POST /api/auth/logout`, `POST /api/auth/password` `{current-password,password}`.
  - `GET/POST /api/accounts`, `PATCH /api/accounts/:id`, `POST /api/accounts/:id/reset-password` (admin).
- Donors (authenticated): `GET/POST /api/donors`, `GET/PUT /api/donors/:id`,
  `GET /api/donors/:id/history`.

Added by the import feature (branch 35+, superset on 37):
- `POST /api/imports/upload` (multipart; `source=bank`, `separator=,|;` for CSV).
- `GET /api/imports/:id/rows?limit=&offset=`.
- `GET /api/imports/:id` (batch), `GET /api/imports/review` (queue, 37),
  `GET /api/imports/:id/rows/:worksheet/:row/comparison?donor-id=` (37).

### Auth + CSRF mechanics (critical for the client)

Two cookies: `alma-session` (session token) and `alma-csrf` (signed CSRF token).
- Every response sets/refreshes `alma-csrf`. `GET /api/auth/session` returns the
  csrf value in the body too (same value as the cookie).
- Mutations (non-GET) require ALL of: valid `alma-csrf` cookie, header
  `X-CSRF-Token` == that cookie value, and header `Origin` == the app origin
  `http://127.0.0.1:<http-port>`. Authenticated non-login mutations also require
  the session's stored csrf-digest to match — keep the same `alma-csrf` cookie
  across login and later calls (an httpx cookie jar does this automatically).
- Missing/!= CSRF → 403; wrong Origin → 403; no session → 401.
- Body limit: non-GET bodies capped at 16 KB (`wrap-body-limit`), EXCEPT imports
  upload which allows up to ~6 MB body / 5 MB file (`imports/limits.clj`).

### Admin provisioning (no interactive bootstrap in tests)

First admin is normally created by interactive `bb create-admin`. For tests,
provision non-interactively, then rotate the forced temp password:
1. Clojure eval of `service/bootstrap!` to create a known-username admin and
   capture the random temporary password. Example form (run from the app repo,
   base deps, env with `ALMA_DB_PASSWORD_FILE`, `ALMA_DB_PORT`, and the default
   `.secrets/auth-secret`):
   ```clojure
   (require '[alma-spei.api.auth.service :as s]
            '[alma-spei.api.config :as c]
            '[alma-spei.api.db.core :as db])
   (println (:temporary-password
             (s/bootstrap! (db/datasource (:database (c/load-config)))
                           {:username "qa.admin" :display-name "QA Admin"})))
   ```
   Run: `clojure -Srepro -M -i <abs-path-to-provision.clj>` (cwd = app repo).
2. The admin has `password-change-required=true`; donor/import calls return 403
   `password-change-required` until rotated.
3. Client flow: `GET /api/auth/session` (get csrf) → `POST /api/auth/login`
   (temp) → `POST /api/auth/password` `{current-password:temp, password:KNOWN}`
   (issues a fresh session, clears the flag). Then the session is usable.
   Pick a KNOWN password meeting policy: 8–128 chars, ≥1 uppercase, ≥1 digit,
   ≥1 symbol, no spaces (e.g. `QaAdmin!2026xyz`).

Password policy (contracts/auth.cljc): username `^[A-Za-z0-9._-]{3,64}$`.
Throttle: login 5/15min per username; password-change 5/15min per user — don't
spam wrong logins in tests.

### Bank CSV shape (for upload fixtures)

`date;sender;description;amount`, `;` separator. Dates accept `YYYY-MM-DD` and
`DD.MM.YYYY`; amount accepts comma or dot decimals (`12,3400`, `-2.50`). Empty
trailing lines are skipped (`skipped-empty-rows`). Invalid row error codes:
`invalid-date`, `missing-sender`, `invalid-amount`, `invalid-sender`,
`invalid-description`. See `dev/alma_spei/dev/bank_fixtures.clj` (`sample-csv`)
and `test/integration/.../bank_upload_test.clj` for exact multipart shape and
expected responses — mirror those assertions in Python.

Multipart upload headers/cookies needed: `Content-Type: multipart/form-data;
boundary=...`, `Origin`, `X-CSRF-Token`, cookies `alma-session` + `alma-csrf`,
field `source=bank` (+ `separator=;` for CSV), one `file` part.

## Planned client architecture (encapsulation)

Build under `src/alma_spei_tests/`:
- `http/session.py` → `AuthSession`: owns the httpx client, cookie jar, origin
  header, CSRF handling, and `login_as_admin()` (login + forced password change).
- `clients/base.py` `BaseClient`; `clients/auth.py` `AuthClient`;
  `clients/donors.py` `DonorsClient`; `clients/imports.py` `ImportsClient`.
- `clients/facade.py` `AlmaSpeiApi`: composes the sub-clients over one session.
- `db/queries.py`: encapsulated read queries (extend existing `db/client.py`).
- `data/factories.py`: extend — synthetic donors + a bank-CSV builder
  (optionally xlsx via openpyxl; keep minimal).
- `pages/`: `login_page.py`, `donors_page.py`, `imports_page.py`,
  `review_page.py` (reuse `base_page.py`). Read the dev UI under
  `wt/dev/36|37/src/ui/alma_spei/ui/...` for exact Polish strings/selectors.
- `steps/`: `auth_steps.py`, `donors_steps.py`, `imports_steps.py`.
- `constants.py`: extend — endpoint paths, status codes, error codes, Polish
  messages, the known admin password.
- `config.py`: extend — admin username/known password, origin == base_url.
- `orchestration/stack.py`: extend `up()` to provision the admin after migrate;
  expose creds; default the real run SERIAL (xdist multi-worker bring-up races —
  run the app-backed suite with `-n0`).

Keep the existing conventions (AGENTS.md): OOP test classes, numbered steps block
at top, assertion helpers (assertpy `.described_as(...).is_equal_to(...)`),
soft assertions, constants, type hints except `-> None`, no
`from __future__ import annotations`.

## Progress

- [x] Step 1 (tests-`main`): client layer (`http/session.py` AuthSession,
  `clients/*` + `AlmaSpeiApi` facade with `sign_in`), config/constants/data/db
  extensions, `DbQueries`, contract mini-DSL (`contracts/schema.py`), page
  objects (shell, auth panel, donor list + card), steps, conftests, admin
  provisioning in `Stack.up()`, and health/errors/auth/password/accounts/donor
  API + contract + DB + e2e tests. Verified offline only (collection, ruff,
  fake-backend check of CSRF/cookie mechanics) - not yet run against the app.

### Findings while building step 1 (keep in mind)

- Logins are throttled **per peer address too: 30 per 15 min**, counted on
  every attempt (success included) and never cleared on success. Everything
  shares 127.0.0.1, so tests borrow sessions (`signed_in_page`,
  `share_session_with_browser`) and the throttle test's fixture clears
  `auth_throttle_buckets` afterwards. Budget is ~22 logins for the main suite.
- No donor delete/archive endpoint: `donor_factory` archives via DB
  (`UPDATE donors SET is_active=false`, granted to the app role) on teardown;
  tests isolate by a per-test `tag` in donor names and search by it.
- `POST /api/auth/logout` and `/api/accounts/:id/reset-password` need a JSON
  `{}` body (closed empty map), not an empty body.
- Donor endpoints don't refresh the `alma-csrf` cookie; auth endpoints do.
- assertpy's dynamic `has_<key>()` can't address hyphenated JSON keys.
- `role="status"` appears several times on the root page; the shell's own one
  is `main > p[role="status"]`.

- [x] Step 2 (`trello/35-bank-parser`): `ImportsClient` (multipart upload,
  retry, staged-row report), `data/bank.py` (synthetic CSV + stdlib-only XLSX
  builder mirroring the app's fixture), import contracts (`BATCH` incl.
  `counts-valid?`), import `DbQueries`, `imports_steps`, `staged_upload`
  fixture; API (upload/rejections/authz, row report, retry), contract and DB
  staging tests. Verified offline only.

### Findings while building step 2

- The backend refuses byte-identical files (409 `duplicate-file`), so every
  upload embeds the test `tag`; the blank-only "no rows" file encodes the tag in
  whitespace (`blank_only_csv`). Staged imports cannot be deleted (no endpoint,
  no DELETE grant) - no teardown, uniqueness keeps runs independent.
- Upload error bodies may add `batch-id`/`batch`; use `assert_error_includes`.
- **Likely app bug on Windows**: `http/imports.clj` creates the temp upload dir
  with `PosixFilePermissions` file attributes, which a Windows JVM rejects
  (`UnsupportedOperationException`) -> every upload would 500. If uploads fail
  that way in step 5, report it to dev rather than weakening tests.

- [x] Step 3 (`trello/36-import-upload`): `ImportsPage` page object (form,
  summary, paged report, retry confirmation; exact-text matching for summary
  labels and row refs), upload UI steps, and e2e tests for navigation, CSV
  separator gating, client-side file-type refusal, CSV/XLSX report, invalid
  rows with Polish reasons, paging past 25 rows, duplicate alert and the
  confirmed retry flow. Verified offline only.

- [x] Step 4 (`trello/37-review-queue`): review client methods (queue, batch,
  comparison), `BATCH_RESPONSE`/`QUEUE_RESPONSE`/`COMPARISON_RESPONSE`
  contracts, `ReviewPage` page object and review UI steps; API tests (queue
  order/paging/validation/authz, batch reads, comparison incl. invalid and
  archived rows, locator/query validation, 409 for non-review batches),
  contract tests, a DB test that reviewing writes nothing, and e2e tests (queue
  progress, open by entry / upload link / deep link, no preselected donor,
  side-by-side comparison, invalid-row notice). Verified offline only.
  Note: the review UI's row `<select>` starts with no matching value, so tests
  pick row 2 (picking the displayed first option may not fire React's change).

## Next steps (in order)

1. On tests-`main`: build the client layer + extend config/constants/data/db,
   write health + auth + donors (+ accounts) tests, rebuild `conftest.py`
   session fixtures (stack → logged-in `AlmaSpeiApi` facade → db). Commit (no
   co-author).
2. `git worktree add ../wt/tests/35 -b trello/35-bank-parser main` (from the
   tests repo). Add imports API + DB staging tests. Commit (co-author Dewiant112).
3. `../wt/tests/36` from `trello/35-bank-parser`. Add upload-UI Playwright tests.
   Commit (no co-author).
4. `../wt/tests/37` from `trello/36-import-upload`. Add review-queue + comparison
   API + UI tests. Commit (co-author Dewiant112).
5. Install toolchain via Scoop; `uv sync`; `uv run playwright install`; run the
   suite serially against each paired dev worktree
   (`ALMA_APP_REPO=...\wt\dev\35 uv run pytest -n0 ...`). Iterate to green.
6. Once Trello MCP is connected: file test tickets.

## Environment facts

- `bb init` now creates 4 secrets incl. `.secrets/auth-secret` (≥32 bytes).
- App honours `ALMA_HTTP_PORT` / `ALMA_DB_PORT` / `ALMA_DB_*` overrides; test
  defaults: HTTP 3100, DB 55432, compose project `alma-spei-tests` (isolated).
- Deps added in dev: `buddy/buddy-hashers` (password hashing). Aliases:
  `:create-admin`, `:seed-demo` (needs an existing admin username; loads 20
  donors + 30 payments).

## Step 5 status (2026-11-11): blocked on the toolchain install

Steps 1-4 are committed on `main` and the three stacked test branches. The
Scoop bootstrap (`irm get.scoop.sh | iex`) was refused by the session's safety
classifier, so nothing app-backed has run yet. Machine state: no Scoop, uv,
JDK 25, Clojure CLI or Babashka; Java 8, Node 22.21 (app pins 24; `npm ci`
only warns), npm 10.9 and Docker Desktop (installed, not running); no
Playwright browsers yet. The `.venv` in this repo already holds all Python deps
(ruff too) and works from the worktrees (`pythonpath = ["src"]` picks the
worktree's own package first).

Orchestration fixed for this machine on `main` (and rebased into the
branches): commands are resolved via `shutil.which` so Windows shims
(`npm.cmd`, `clojure.cmd`) launch, `npm ci --ignore-scripts` runs when the app
checkout has no `node_modules`, and npm is part of the preflight.

To finish step 5 (run by the maintainer, PowerShell):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
irm get.scoop.sh | iex
scoop bucket add java
scoop install temurin-lts-jdk          # JDK 25 LTS; or temurin25-jdk if listed
scoop bucket add scoop-clojure https://github.com/littleli/scoop-clojure
scoop install clj-deps babashka uv     # check `clojure -version`, else set ALMA_CLOJURE_CMD
# start Docker Desktop, then:
cd C:\STUDIA\mpt\alma-spei-tests
uv sync
uv run playwright install chromium
uv run pytest -n0                                   # main vs ..\alma-spei
cd ..\wt\tests\35
$env:ALMA_APP_REPO = "C:\STUDIA\mpt\wt\dev\35"
..\..\..\alma-spei-tests\.venv\Scripts\python -m pytest -n0   # repeat for 36, 37
```

Expect first-run triage: the Windows POSIX temp-dir issue on uploads (see
step 2 findings), the buddy-hashers hash prefix asserted in
`test_auth_persistence.py`, and any selector drift in the e2e page objects.

## Skills

Installed at user level for future sessions: `~/.claude/skills/caveman` and
`~/.claude/skills/ponytail` (voice/approach skills; off by default, invoked by
name). They do not change the plan above.
