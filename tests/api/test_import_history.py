"""API tests for the read additions behind the confirmation and history screens (task 40).

``GET /api/imports/capabilities`` tells the screen whether commits are possible
and in which mode, without revealing configuration. The history names each
batch's uploader by the current display label, and outcomes carry it too.
"""

from http import HTTPStatus
from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import SYNTHETIC_BACKUP_ADAPTER, ApiErrorPayload
from alma_spei_tests.steps import execution_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Import history")
class TestCapabilities(BaseApiTest):
    def test_the_orchestrated_app_commits_in_synthetic_mode(self, api: AlmaSpeiApi):
        # 1. Read the import capabilities
        # 2. Verification: 200; commits enabled in the labelled synthetic test mode only
        response = execution_steps.read_capabilities(api)
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "reading the import capabilities")
            assert_that(response.json()).described_as(
                "the test stack should allow synthetic commits only"
            ).is_equal_to({"commit-enabled": True, "mode": SYNTHETIC_BACKUP_ADAPTER})

    def test_anonymous_client_cannot_read_capabilities(self, anonymous_api: AlmaSpeiApi):
        # 1. Read the capabilities without signing in
        # 2. Verification: 401 unauthenticated
        response = execution_steps.read_capabilities(anonymous_api)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


@allure.feature("Import history")
class TestHistory(BaseApiTest):
    def test_the_newest_upload_heads_the_history_with_its_uploader(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], settings: Settings
    ):
        # 1. Stage an upload (fixture)
        # 2. Read the first history entry
        # 3. Verification: it is this batch; its uploader is listed by display name
        body = execution_steps.read_history(api, limit=1).json()
        batch = body["batches"][0]
        uploaders = {u["id"]: u["display-name"] for u in body["uploaders"]}
        with soft_assertions():
            assert_that(batch["id"]).described_as(
                "the newest upload should head the history"
            ).is_equal_to(staged_upload["batch"]["id"])
            assert_that(uploaders.get(batch["created-by"])).described_as(
                "the uploader should be named by the current display name"
            ).is_equal_to(settings.admin_display_name)

    def test_an_outcome_names_the_uploader(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], settings: Settings
    ):
        # 1. Read the outcome of a staged (uncommitted) batch
        # 2. Verification: the uploader's display name, no commit and no undo yet
        body = execution_steps.read_outcome(api, staged_upload["batch"]["id"]).json()
        assert_that((body["uploaded-by-name"], body["commit"], body["undo"])).described_as(
            "a staged batch should have only its upload context"
        ).is_equal_to((settings.admin_display_name, None, None))
