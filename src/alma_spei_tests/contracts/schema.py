"""A tiny schema vocabulary for mirroring the app's Malli contracts in Python.

Only what the contracts use: closed maps and enums. ``schema.explain(value)`` returns
human-readable violations with a JSON path; an empty list means valid.
"""

from collections.abc import Mapping


class Schema:
    def explain(self, value: object, path: str = "$") -> list[str]:
        raise NotImplementedError


class Enum(Schema):
    def __init__(self, *values: str):
        self.values = values

    def explain(self, value: object, path: str = "$") -> list[str]:
        if value in self.values:
            return []
        return [f"{path}: must be one of {list(self.values)}, got {value!r}"]


class ClosedMap(Schema):
    """A JSON object with exactly the declared keys (``optional`` may be absent)."""

    def __init__(self, fields: Mapping[str, Schema], optional: Mapping[str, Schema] | None = None):
        self.fields = dict(fields)
        self.optional = dict(optional or {})

    def explain(self, value: object, path: str = "$") -> list[str]:
        if not isinstance(value, dict):
            return [f"{path}: expected a JSON object, got {type(value).__name__}"]
        problems: list[str] = []
        extra = set(value) - set(self.fields) - set(self.optional)
        if extra:
            problems.append(f"{path}: unexpected key(s) {sorted(extra)}")
        missing = set(self.fields) - set(value)
        if missing:
            problems.append(f"{path}: missing key(s) {sorted(missing)}")
        for key, schema in {**self.fields, **self.optional}.items():
            if key in value:
                problems.extend(schema.explain(value[key], f"{path}.{key}"))
        return problems
