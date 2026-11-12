"""Reusable steps for sessions and account administration."""

from http import HTTPStatus
from typing import Any

import httpx

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.data import ProvisionedAccount, SyntheticAccount
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.steps import step


# --- session ------------------------------------------------------------------
@step("Inspect the current session GET /api/auth/session")
def inspect_session(api: AlmaSpeiApi) -> httpx.Response:
    return api.auth.session()


@step("Log in as {username}")
def login(
    api: AlmaSpeiApi, username: str, password: str, *, headers: HeaderOverrides | None = None
) -> httpx.Response:
    return api.auth.login(username, password, headers=headers)


@step("Submit a raw login body")
def login_with(api: AlmaSpeiApi, body: object) -> httpx.Response:
    return api.auth.login_with(body)


@step("Log out")
def logout(api: AlmaSpeiApi) -> httpx.Response:
    return api.auth.logout()


@step("Change the password")
def change_password(api: AlmaSpeiApi, current_password: str, new_password: str) -> httpx.Response:
    return api.auth.change_password(current_password, new_password)


@step("Sign in as {username} (rotating a temporary password if required)")
def sign_in(
    api: AlmaSpeiApi, username: str, password: str, *, new_password: str | None = None
) -> dict[str, Any]:
    return api.sign_in(username, password, new_password=new_password)


# --- accounts -----------------------------------------------------------------
@step("List accounts")
def list_accounts(api: AlmaSpeiApi) -> httpx.Response:
    return api.accounts.list()


@step("Request account {account.username}")
def request_account(api: AlmaSpeiApi, account: SyntheticAccount) -> httpx.Response:
    return api.accounts.create(
        account.username, account.display_name, administrator=account.administrator
    )


@step("Create account {account.username}")
def create_account(api: AlmaSpeiApi, account: SyntheticAccount) -> ProvisionedAccount:
    """Create the account (setup step: fails loudly unless HTTP 200)."""
    response = api.accounts.create(
        account.username, account.display_name, administrator=account.administrator
    )
    body = expect_status(response, HTTPStatus.OK, "Create account").json()
    return ProvisionedAccount(account, body["user"]["id"], body["temporary-password"])


@step("Edit account {account_id}")
def edit_account(
    api: AlmaSpeiApi, account_id: str, display_name: str, *, active: bool, administrator: bool
) -> httpx.Response:
    return api.accounts.edit(account_id, display_name, active=active, administrator=administrator)


@step("Deactivate account {account_id}")
def deactivate_account(api: AlmaSpeiApi, account_id: str, display_name: str):
    response = api.accounts.edit(account_id, display_name, active=False, administrator=False)
    expect_status(response, HTTPStatus.OK, "Deactivate account")


@step("Reset the password of account {account_id}")
def reset_password(api: AlmaSpeiApi, account_id: str) -> httpx.Response:
    return api.accounts.reset_password(account_id)
