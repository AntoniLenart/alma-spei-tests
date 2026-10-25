"""Load and resolve execution groups from ``execution-groups.yaml``.

The YAML maps a group name to a pytest marker expression plus a parallel flag.
``conftest.py`` turns the resolved group into runtime options (-m marker
expression and the xdist -n / --dist settings). Keeping this parsing in the
package (not in conftest) keeps the hook code thin and unit-testable.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from alma_spei_tests.config import REPO_ROOT

DEFAULT_GROUPS_FILE = REPO_ROOT / "execution-groups.yaml"


@dataclass(frozen=True)
class GroupSpec:
    name: str
    markers: str
    parallel: bool = True
    run_disruptive: bool = False


def load_groups(path: Path | None = None) -> dict[str, dict]:
    path = path or DEFAULT_GROUPS_FILE
    if not path.exists():
        raise FileNotFoundError(f"Execution groups file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = data.get("groups")
    if not isinstance(groups, dict):
        raise ValueError(f"{path} must contain a top-level 'groups' mapping")
    return groups


def resolve_group(name: str, path: Path | None = None) -> GroupSpec:
    groups = load_groups(path)
    if name not in groups:
        available = ", ".join(sorted(groups)) or "(none)"
        raise KeyError(f"Unknown execution group {name!r}. Available: {available}")
    raw = groups[name] or {}
    markers = raw.get("markers")
    if not markers:
        raise ValueError(f"Group {name!r} must define a 'markers' expression")
    return GroupSpec(
        name=name,
        markers=str(markers),
        parallel=bool(raw.get("parallel", True)),
        run_disruptive=bool(raw.get("disruptive", False)),
    )
