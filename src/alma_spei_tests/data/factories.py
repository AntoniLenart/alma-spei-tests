"""Synthetic donors and accounts, generated with Faker's Polish locale.

IMPORTANT (per the app's AGENTS.md and GDPR rules): this suite must NEVER use
real personal data. Every value here is invented by Faker and is not intended
to represent any real person, business or organization. Do not seed these
factories from, or compare them against, real donor records.

Factories are deterministic when given a seed. Tests that share one database
isolate themselves with a ``unique_tag()`` embedded in donor names, then search
by that tag.
"""

import dataclasses
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from faker import Faker

from alma_spei_tests.constants import EntityType

_LOCALE = "pl_PL"

#: Marks synthetic test records so they are recognisable in any listing.
TAG_PREFIX = "QA-"


def seeded_faker(seed: int | None = None) -> Faker:
    """Return a Faker instance pinned to the Polish locale, optionally seeded."""
    fake = Faker(_LOCALE)
    if seed is not None:
        fake.seed_instance(seed)
    return fake


def unique_tag() -> str:
    """A short random marker, e.g. ``QA-3f9a2c1b``, for isolating test data."""
    return f"{TAG_PREFIX}{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class DonorProfile:
    """The editable donor fields, mirroring the create/update contract."""

    entity_type: EntityType
    name: str
    city: str
    first_name: str | None = None
    street: str | None = None
    postal_code: str | None = None
    province: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        """The JSON body for POST /api/donors (kebab-case keys)."""
        return {
            "entity-type": self.entity_type.value,
            "name": self.name,
            "first-name": self.first_name,
            "street": self.street,
            "postal-code": self.postal_code,
            "city": self.city,
            "province": self.province,
        }

    def to_update_payload(self, version: int) -> dict[str, object]:
        """The JSON body for PUT /api/donors/:id (profile + optimistic version)."""
        return {**self.to_payload(), "version": version}

    def with_changes(self, **changes: Any) -> "DonorProfile":
        return dataclasses.replace(self, **changes)


#: The ``donor_factory`` fixture: creates a donor via the API, returns its JSON.
DonorFactory = Callable[[DonorProfile], dict[str, Any]]


def new_donor_profile(
    entity_type: EntityType = EntityType.INDIVIDUAL,
    *,
    tag: str | None = None,
    seed: int | None = None,
    fake: Faker | None = None,
) -> DonorProfile:
    """One synthetic donor; ``tag`` is appended to the name for searchability."""
    fake = fake or seeded_faker(seed)
    first_name = None
    if entity_type is EntityType.INDIVIDUAL:
        first_name = fake.first_name()
        label = f"{first_name} {fake.last_name()}"
    elif entity_type is EntityType.BUSINESS:
        label = fake.company()
    else:
        label = f"Fundacja {fake.last_name()}"
    return DonorProfile(
        entity_type=entity_type,
        name=f"{label} {tag}" if tag else label,
        first_name=first_name,
        street=fake.street_address(),
        postal_code=fake.postcode(),
        city=fake.city(),
        province=fake.administrative_unit(),
    )


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
