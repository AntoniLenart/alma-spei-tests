"""Synthetic donor data, generated with Faker's Polish locale.

IMPORTANT (per the app's AGENTS.md and GDPR rules): this suite must NEVER use
real personal data. Every value here is invented by Faker and is not intended
to represent any real person, business or organization. Do not seed these
factories from, or compare them against, real donor records.

Factories are deterministic when given a seed, so a test can reproduce the same
synthetic population across runs and workers.
"""

import random
from dataclasses import dataclass, field
from enum import Enum

from faker import Faker

_LOCALE = "pl_PL"


class DonorType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ORGANIZATION = "organization"


@dataclass(frozen=True)
class Address:
    street: str
    postal_code: str
    city: str
    province: str


@dataclass(frozen=True)
class SyntheticDonor:
    """A single invented donor. Marked synthetic to avoid any confusion."""

    donor_type: DonorType
    display_name: str
    address: Address
    synthetic: bool = field(default=True)


def seeded_faker(seed: int | None = None) -> Faker:
    """Return a Faker instance pinned to the Polish locale, optionally seeded."""
    fake = Faker(_LOCALE)
    if seed is not None:
        fake.seed_instance(seed)
    return fake


def _address(fake: Faker) -> Address:
    return Address(
        street=fake.street_address(),
        postal_code=fake.postcode(),
        city=fake.city(),
        province=fake.administrative_unit(),
    )


def new_donor(
    donor_type: DonorType = DonorType.INDIVIDUAL,
    *,
    seed: int | None = None,
    fake: Faker | None = None,
) -> SyntheticDonor:
    """Create one synthetic donor of the given type."""
    fake = fake or seeded_faker(seed)
    if donor_type is DonorType.INDIVIDUAL:
        name = fake.name()
    elif donor_type is DonorType.BUSINESS:
        name = fake.company()
    else:
        name = f"Fundacja {fake.last_name()}"
    return SyntheticDonor(donor_type=donor_type, display_name=name, address=_address(fake))


def new_donors(count: int, *, seed: int | None = None) -> list[SyntheticDonor]:
    """Create a deterministic batch spread across all donor types."""
    fake = seeded_faker(seed)
    rng = random.Random(seed)
    types = list(DonorType)
    return [new_donor(rng.choice(types), fake=fake) for _ in range(count)]
