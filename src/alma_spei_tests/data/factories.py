"""Synthetic accounts, generated with Faker's Polish locale.

IMPORTANT (per the app's AGENTS.md and GDPR rules): this suite must NEVER use
real personal data. Every value here is invented by Faker and is not intended
to represent any real person, business or organization. Do not seed these
factories from, or compare them against, real donor records.

Factories are deterministic when given a seed.
"""

import uuid
from dataclasses import dataclass

from faker import Faker

_LOCALE = "pl_PL"


def seeded_faker(seed: int | None = None) -> Faker:
    """Return a Faker instance pinned to the Polish locale, optionally seeded."""
    fake = Faker(_LOCALE)
    if seed is not None:
        fake.seed_instance(seed)
    return fake


@dataclass(frozen=True)
class SyntheticAccount:
    """A user account to create through the accounts API."""

    username: str
    display_name: str
    administrator: bool = False


def new_account(*, administrator: bool = False, seed: int | None = None) -> SyntheticAccount:
    """A unique, policy-valid synthetic account (username ``qa.<hex>``)."""
    fake = seeded_faker(seed)
    return SyntheticAccount(
        username=f"qa.{uuid.uuid4().hex[:12]}",
        display_name=f"QA {fake.first_name()} {fake.last_name()}",
        administrator=administrator,
    )


@dataclass(frozen=True)
class ProvisionedAccount:
    """An account created through the API, with its one-time temporary password."""

    account: SyntheticAccount
    id: str
    temporary_password: str

    @property
    def username(self) -> str:
        return self.account.username

    @property
    def display_name(self) -> str:
        return self.account.display_name
