# Acceptance scenarios: sign-in and accounts

Preconditions: a fresh stack with the synthetic administrator.

## MAN-A-01: Sign-in only, in Polish, without self-registration

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_accounts_panel.py`. The manual run checks the wording. |

**Steps**

1. Open the app without a session.

**Expected result**

- Only the Polish "Logowanie" form is shown, with no navigation and nothing offering to create an account.

## MAN-A-02: A temporary password must be changed first

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_accounts_panel.py`, `tests/api/test_security_access.py`. |

**Steps**

1. As the administrator, create a staff account in "Konta użytkowników" and note the one-time password.
2. Sign in as that account in a private window.
3. Try a weak new password, then a compliant one.

**Expected result**

- The temporary password leads straight to the password change.
- A weak password is refused with the Polish policy message.
- The donor register and imports become reachable only after the change.

## MAN-A-03: Reset and deactivation end the account's sessions

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_accounts_panel.py`. |

**Steps**

1. Keep the staff account signed in in the private window.
2. As the administrator, choose "Resetuj hasło" for it and confirm. Then, in a second round, untick "Konto aktywne", save and confirm.
3. Act in the staff window after each step.

**Expected result**

- After the reset, a new one-time password is shown once, and the staff window is signed out at its next action.
- After deactivation, the account cannot sign in.
