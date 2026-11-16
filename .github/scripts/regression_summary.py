"""Markdown summary of a regression run, from its JUnit XML files (for $GITHUB_STEP_SUMMARY).

Usage: python3 regression_summary.py <junit.xml> [<junit.xml> ...]
Missing files (a step that never ran) are reported, not fatal.
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

#: At most this many failing tests are listed by name.
MAX_LISTED = 30


def main(paths: list[str]) -> int:
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    failed: list[str] = []
    missing: list[str] = []
    for path in paths:
        if not Path(path).is_file():
            missing.append(Path(path).name)
            continue
        for suite in ET.parse(path).getroot().iter("testsuite"):
            for key in totals:
                totals[key] += int(suite.get(key, 0))
            for case in suite.iter("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    failed.append(f"{case.get('classname')}::{case.get('name')}")

    passed = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    dev = os.environ.get("DEV_REF", "?")
    sha = os.environ.get("DEV_SHA", "")[:7]
    print(f"## Full regression - dev `{dev}` @ `{sha}`\n")
    print("| Passed | Failed | Errors | Skipped | Total |")
    print("|---:|---:|---:|---:|---:|")
    print(
        f"| {passed} | {totals['failures']} | {totals['errors']} | {totals['skipped']}"
        f" | {totals['tests']} |\n"
    )
    if failed:
        print("### Failing tests\n")
        for name in failed[:MAX_LISTED]:
            print(f"- `{name}`")
        if len(failed) > MAX_LISTED:
            print(f"- ... and {len(failed) - MAX_LISTED} more (see the Allure report)")
        print()
    if missing:
        print(f"Not run: {', '.join(missing)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
