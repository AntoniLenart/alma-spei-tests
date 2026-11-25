# Security tests

Systematic security checks of the MVP against the OWASP Top 10 (2021), run on our
own stack only (local or CI) with synthetic data. Findings are filed as bug
cards with a severity, and the matching checks are **strict expected failures**
(`xfail(strict=True)`) until the bug is fixed. A fix makes the test pass
unexpectedly, which reminds us to remove the marker.

## Coverage

| Area | OWASP | Tests |
| --- | --- | --- |
| Access per route: anonymous → 401, temporary password → 403, staff on account routes → 403 | A01 Broken access control | `tests/api/test_security_access.py` (every route of `alma_spei_tests.routes`) |
| CSRF on every mutating route: no token, forged token, foreign origin, no origin → 403 | A01 | `tests/api/test_security_csrf.py` |
| Sessions, cookies, expiry, logout, no self-registration, login throttle, no-store, Argon2id, token digests | A02 / A07 | Existing `tests/api/test_auth_hardening.py`, `test_auth_session.py`, `test_auth_password.py`, `tests/db/test_auth_schema.py`, `tests/db/test_auth_persistence.py` |
| SQL injection in filters, ids and paging; text stored as typed (SQL- and formula-looking) | A03 Injection | `tests/api/test_security_injection.py`, plus `test_donor_list.py` (literal search) |
| Stored XSS through donor names, import senders and file names | A03 | `tests/e2e/test_security_xss.py` |
| Upload: paths and control characters in names, markup in names, extensions, XXE, billion laughs, zip bomb, too many entries, traversal entries, macros, external links | A04 / A05 / A08 | `tests/api/test_security_upload.py`, plus `test_bank_upload.py` (size limit) |
| Protective headers on every kind of response, server version, error bodies without internals | A05 Security misconfiguration | `tests/api/test_security_headers.py` |
| Least-privileged database role | A05 | `tests/db/test_security_role.py`, plus each schema's grant tests |
| Dependencies of this suite | A06 Vulnerable components | `Dependency audit` job in `.github/workflows/checks.yml` (`pip-audit`) |
| Passive scan of the running app | all | `tests/api/test_zap_baseline.py`, the `zap` group of `.github/workflows/regression.yml` |

## OWASP ZAP baseline

The ZAP baseline spiders the app for a minute and reports passive findings. It
runs in a container with host networking, so it only works on Linux. The
regression workflow runs it after the disruptive tests:

```sh
ALMA_TEST_ZAP_SCAN=1 uv run pytest --group zap
```

The HTML and JSON reports are attached to the Allure result and kept with the
run's artifacts (`reports/zap`). A high-risk alert fails the test; medium and
low alerts are reviewed and filed.

## Findings

| Finding | Severity | Check |
| --- | --- | --- |
| No Content-Security-Policy and no framing ban (clickjacking) | Medium | `test_the_ui_page_restricts_scripts_and_cannot_be_framed` (xfail) |
| The `Server` header names Jetty and its version | Low | `test_no_response_names_the_server_software` (xfail) |
| Commit, undo, backup receipt and password change validate the body before the session (field names leak to anonymous clients) | Low | the four routes in `test_security_access.py` (xfail) |

## Not tested here, and why

- **The Secure cookie flag** waits for TLS. The loopback stack leaves it off on
  purpose (`test_the_secure_flag_waits_for_tls`).
- **HSTS** also needs TLS.
- **Formula escaping in exports** waits for exports, which do not exist yet.
  Formula-looking text is checked to be stored as typed.
- **Other people's infrastructure** is never scanned.
