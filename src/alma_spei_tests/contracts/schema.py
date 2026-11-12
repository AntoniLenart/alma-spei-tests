"""A tiny schema vocabulary for mirroring the app's Malli contracts in Python.

Only what the contracts use: closed maps, maybe, vectors, enums, regexes,
bounded ints, strings and booleans. ``schema.explain(value)`` returns
human-readable violations with a JSON path; an empty list means valid.
"""

import re
from collections.abc import Callable, Mapping

#: Malli's safe-maximum for integer fields (JavaScript Number.MAX_SAFE_INTEGER).
SAFE_MAXIMUM = 9007199254740991


class Schema:
    def explain(self, value: object, path: str = "$") -> list[str]:
        raise NotImplementedError


class Predicate(Schema):
    def __init__(self, description: str, check: Callable[[object], bool]):
        self.description = description
        self.check = check

    def explain(self, value: object, path: str = "$") -> list[str]:
        return [] if self.check(value) else [f"{path}: expected {self.description}, got {value!r}"]


STRING = Predicate("a string", lambda v: isinstance(v, str))
BOOLEAN = Predicate("a boolean", lambda v: isinstance(v, bool))
NONBLANK_STRING = Predicate("a non-blank string", lambda v: isinstance(v, str) and bool(v.strip()))


class Int(Schema):
    def __init__(self, minimum: int = -SAFE_MAXIMUM, maximum: int = SAFE_MAXIMUM):
        self.minimum = minimum
        self.maximum = maximum

    def explain(self, value: object, path: str = "$") -> list[str]:
        if isinstance(value, bool) or not isinstance(value, int):
            return [f"{path}: expected an integer, got {value!r}"]
        if not self.minimum <= value <= self.maximum:
            return [f"{path}: expected {self.minimum}..{self.maximum}, got {value}"]
        return []


class Enum(Schema):
    def __init__(self, *values: str):
        self.values = values

    def explain(self, value: object, path: str = "$") -> list[str]:
        if value in self.values:
            return []
        return [f"{path}: must be one of {list(self.values)}, got {value!r}"]


class Regex(Schema):
    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)

    def explain(self, value: object, path: str = "$") -> list[str]:
        if isinstance(value, str) and self.pattern.fullmatch(value):
            return []
        return [f"{path}: expected a string matching {self.pattern.pattern}, got {value!r}"]


class Maybe(Schema):
    def __init__(self, inner: Schema):
        self.inner = inner

    def explain(self, value: object, path: str = "$") -> list[str]:
        return [] if value is None else self.inner.explain(value, path)


class Vector(Schema):
    def __init__(self, item: Schema):
        self.item = item

    def explain(self, value: object, path: str = "$") -> list[str]:
        if not isinstance(value, list):
            return [f"{path}: expected an array, got {type(value).__name__}"]
        problems: list[str] = []
        for index, item in enumerate(value):
            problems.extend(self.item.explain(item, f"{path}[{index}]"))
        return problems


class AllOf(Schema):
    """Every schema must hold (Malli ``[:and ...]``)."""

    def __init__(self, *schemas: Schema):
        self.schemas = schemas

    def explain(self, value: object, path: str = "$") -> list[str]:
        problems: list[str] = []
        for schema in self.schemas:
            problems.extend(schema.explain(value, path))
        return problems


class Const(Schema):
    """Exactly one value (Malli ``:nil`` / ``[:= x]``)."""

    def __init__(self, expected: object):
        self.expected = expected

    def explain(self, value: object, path: str = "$") -> list[str]:
        return (
            [] if value == self.expected else [f"{path}: expected {self.expected!r}, got {value!r}"]
        )


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
