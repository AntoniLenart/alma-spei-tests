"""``AlmaSpeiApi``: one authenticated session, every endpoint group, and workflows.

    api = AlmaSpeiApi.connect(base_url, timeout=10)   # anonymous, CSRF primed
    api.sign_in("qa.admin", temporary, new_password=KNOWN_PASSWORD)
    api.donors.create(profile.to_payload())

The sub-clients share the facade's ``AuthSession``, so logging in through
``api.auth`` authenticates ``api.donors`` too.
"""

from http import HTTPStatus
from types import TracebackType
from typing import Any

from alma_spei_tests.clients.accounts import AccountsClient
from alma_spei_tests.clients.auth import AuthClient
from alma_spei_tests.clients.base import ApiError, expect_status
from alma_spei_tests.clients.donors import DonorsClient
from alma_spei_tests.clients.health import HealthClient
from alma_spei_tests.clients.imports import ImportsClient
from alma_spei_tests.http import AuthSession


class AlmaSpeiApi:
    def __init__(self, session: AuthSession):
        self.session = session
        self.health = HealthClient(session)
        self.auth = AuthClient(session)
        self.accounts = AccountsClient(session)
        self.donors = DonorsClient(session)
        self.imports = ImportsClient(session)

    @classmethod
    def connect(cls, base_url: str, *, timeout: float) -> "AlmaSpeiApi":
        """A fresh anonymous session with its CSRF cookie already issued."""
        api = cls(AuthSession(base_url, timeout=timeout))
        expect_status(api.auth.session(), HTTPStatus.OK, "Prime CSRF token")
        return api

    # --- lifecycle ------------------------------------------------------------
    def __enter__(self) -> "AlmaSpeiApi":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        self.close()

    def close(self):
        self.session.close()

    # --- workflows ------------------------------------------------------------
    def sign_in(
        self, username: str, password: str, *, new_password: str | None = None
    ) -> dict[str, Any]:
        """Log in and return the principal.

        If the account still has a temporary password, rotate it to
        ``new_password`` (required in that case) - the backend refuses donor
        and account calls until it is changed. Rotation issues a fresh session.
        """
        login = expect_status(self.auth.login(username, password), HTTPStatus.OK, "Login")
        user = login.json()["user"]
        if not user["password-change-required"]:
            return user
        if new_password is None:
            raise ApiError("Login (account requires a password change)", login)
        rotated = expect_status(
            self.auth.change_password(password, new_password), HTTPStatus.OK, "Password rotation"
        )
        return rotated.json()["user"]

    def current_user(self) -> dict[str, Any] | None:
        """The principal of this session according to the backend, or None."""
        return expect_status(self.auth.session(), HTTPStatus.OK, "Inspect session").json()["user"]

    def signed_in_user(self) -> dict[str, Any]:
        """The principal of this session; raises ApiError when the backend sees none."""
        response = expect_status(self.auth.session(), HTTPStatus.OK, "Inspect session")
        user = response.json()["user"]
        if user is None:
            raise ApiError("Inspect session (no signed-in user)", response)
        return user
