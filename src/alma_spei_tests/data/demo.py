"""The stable ids of the synthetic demo population (dev/alma_spei/dev/demo_data.clj).

The loader derives every row's id from its kind and number the way Java's
``UUID.nameUUIDFromBytes`` does: a version-3 UUID of the MD5 of
``alma-spei:synthetic-demo:v1:<kind>:<number>``. Its profiles carry ordinary,
invented Polish names, so the tests recognise the demo rows by these ids.
"""

import hashlib
import uuid

from alma_spei_tests.constants import DemoDataset


def stable_demo_id(kind: str, number: int) -> str:
    seed = f"{DemoDataset.ID_NAMESPACE}:{kind}:{number}".encode()
    return str(uuid.UUID(bytes=hashlib.md5(seed, usedforsecurity=False).digest(), version=3))


def demo_donor_ids() -> list[str]:
    """The ids of every demo profile, in the loader's order."""
    return [stable_demo_id("donor", number) for number in range(1, DemoDataset.DONORS + 1)]
