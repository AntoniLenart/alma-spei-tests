"""Health response contract.

Mirrors the app's shared Malli schema:

    ;; src/common/alma_spei/common/contracts/health.cljc
    (def response
      [:map {:closed true}
       [:status [:enum "ok" "unavailable"]]])

A closed map with exactly one key, ``status``, whose value is one of the two
allowed strings. Keep this file in sync when the app's contract changes; the
contract tests exist precisely to catch when a response drifts from it.
"""

from alma_spei_tests.constants import HEALTH_STATUS_VALUES

#: A lightweight description of the closed map, used by validate_health_response.
HEALTH_RESPONSE = {
    "closed": True,
    "fields": {"status": HEALTH_STATUS_VALUES},
}


def validate_health_response(body: object) -> list[str]:
    """Return a list of human-readable violations; empty list means valid."""
    problems: list[str] = []

    if not isinstance(body, dict):
        return [f"expected a JSON object, got {type(body).__name__}"]

    keys = set(body.keys())
    expected_keys = set(HEALTH_RESPONSE["fields"])

    extra = keys - expected_keys
    if extra:  # closed map: no additional keys allowed
        problems.append(f"unexpected key(s): {sorted(extra)}")

    missing = expected_keys - keys
    if missing:
        problems.append(f"missing key(s): {sorted(missing)}")

    if "status" in body and body["status"] not in HEALTH_STATUS_VALUES:
        problems.append(
            f"status must be one of {list(HEALTH_STATUS_VALUES)}, got {body['status']!r}"
        )

    return problems
