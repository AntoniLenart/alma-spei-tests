"""OWASP ZAP baseline scan of the orchestrated stack.

The ZAP baseline spiders the running app for a short while and reports passive
findings (headers, cookies, information leaks). The scan runs in a container
with host networking, so it reaches the loopback-only stack on Linux - the CI
regression workflow runs it as the ``zap`` group (``ALMA_TEST_ZAP_SCAN=1``).
The HTML and JSON reports are attached to the Allure result. A high-risk alert
fails the test; lower risks are kept in the report and reviewed on the card.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import allure
import pytest
from assertpy import assert_that

from alma_spei_tests.config import REPO_ROOT, Settings
from alma_spei_tests.orchestration import Stack
from alma_spei_tests.testbase import BaseApiTest

pytestmark = pytest.mark.zap

#: ZAP's risk codes.
HIGH_RISK = "3"
RISK_NAMES = {"0": "Informational", "1": "Low", "2": "Medium", "3": "High"}

#: Where the scan writes its reports (mounted into the container).
ZAP_REPORTS = REPO_ROOT / "reports" / "zap"
JSON_REPORT = "zap-baseline.json"
HTML_REPORT = "zap-baseline.html"

#: The scan's own spider time (minutes) and the whole run's time limit (seconds).
SPIDER_MINUTES = "1"
SCAN_TIMEOUT_S = 900


@allure.feature("Security: ZAP baseline")
class TestZapBaseline(BaseApiTest):
    def test_the_zap_baseline_finds_no_high_risk_alert(
        self, settings: Settings, stack: Stack, base_url: str
    ):
        # 1. Run the ZAP baseline scan against the running stack
        # 2. Attach its HTML and JSON reports
        # 3. Verification: no high-risk alert
        if not settings.zap_scan:
            pytest.skip("opt-in: set ALMA_TEST_ZAP_SCAN=1 (the CI regression's zap group)")
        if not sys.platform.startswith("linux"):
            pytest.skip("ZAP reaches the loopback stack only with Docker host networking (Linux)")
        alerts = run_baseline(settings, base_url)
        summary = "\n".join(
            f"{RISK_NAMES.get(a['riskcode'], a['riskcode'])}: {a['name']} ({a.get('count', '?')})"
            for a in sorted(alerts, key=lambda a: a["riskcode"], reverse=True)
        )
        allure.attach(summary or "No alerts.", "ZAP alerts", allure.attachment_type.TEXT)
        assert_that([a["name"] for a in alerts if a["riskcode"] == HIGH_RISK]).described_as(
            "the baseline scan should find no high-risk alert"
        ).is_empty()


# --- file-local helpers -------------------------------------------------------
def run_baseline(settings: Settings, base_url: str) -> list[dict]:
    """Run zap-baseline.py in a container and return its alerts."""
    ZAP_REPORTS.mkdir(parents=True, exist_ok=True)
    os.chmod(ZAP_REPORTS, 0o777)  # the container runs as its own user
    command = [
        settings.docker_cmd,
        "run",
        "--rm",
        "--network",
        "host",
        "-v",
        f"{ZAP_REPORTS}:/zap/wrk:rw",
        settings.zap_image,
        "zap-baseline.py",
        "-t",
        base_url,
        "-m",
        SPIDER_MINUTES,
        "-J",
        JSON_REPORT,
        "-r",
        HTML_REPORT,
        "-I",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=SCAN_TIMEOUT_S)
    allure.attach(completed.stdout[-20000:], "ZAP output", allure.attachment_type.TEXT)
    for name, kind in (
        (HTML_REPORT, allure.attachment_type.HTML),
        (JSON_REPORT, allure.attachment_type.JSON),
    ):
        path = ZAP_REPORTS / name
        if path.is_file():
            allure.attach.file(str(path), name, kind)
    report_path: Path = ZAP_REPORTS / JSON_REPORT
    assert_that(report_path.is_file()).described_as(
        f"the scan should write its report (exit {completed.returncode}: {completed.stderr[-500:]})"
    ).is_true()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return [alert for site in report.get("site", []) for alert in site.get("alerts", [])]
