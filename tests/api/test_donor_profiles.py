"""API tests for donor profiles: create, read, versioned update, history, validation."""

import uuid
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import (
    assert_donor_matches_profile,
    assert_donor_validation_error,
    assert_error,
    assert_status,
)
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import (
    INITIAL_DONOR_VERSION,
    ApiErrorPayload,
    AuditAction,
    FieldErrorCode,
)
from alma_spei_tests.data import DonorFactory, DonorProfile
from alma_spei_tests.steps import donors_steps
from alma_spei_tests.testbase import BaseApiTest

#: Not a UUID - the backend answers 404 rather than 400 for malformed ids.
MALFORMED_DONOR_ID = "not-a-uuid"

#: Fails the XX-XXX postal code format.
INVALID_POSTAL_CODE = "SYNTHETIC-REJECTED"

#: Changed name used by the update scenarios.
RENAMED_SUFFIX = " (zmieniony)"


@allure.feature("Donor profiles")
class TestDonorCreation(BaseApiTest):
    @pytest.mark.smoke
    def test_create_returns_the_new_active_donor(
        self, donor_factory: DonorFactory, donor_profile: DonorProfile
    ):
        # 1. Create a synthetic individual donor
        # 2. Verification: the donor echoes the profile, is active and starts at version 1
        donor = donor_factory(donor_profile)
        with soft_assertions():
            assert_donor_matches_profile(donor, donor_profile.to_payload())
            assert_that(donor["is-active"]).described_as("a new donor should be active").is_true()
            assert_that(donor["version"]).described_as(
                "a new donor should start at the initial version"
            ).is_equal_to(INITIAL_DONOR_VERSION)

    def test_create_requires_a_name(self, api: AlmaSpeiApi, donor_profile: DonorProfile, tag: str):
        # 1. Submit a donor without a name
        # 2. Verification: HTTP 400 with a "required" error on name, and nothing is stored
        payload = without(donor_profile.to_payload(), "name")
        response = donors_steps.request_create(api, payload)
        assert_donor_validation_error(response, "name", FieldErrorCode.REQUIRED)
        assert_nothing_stored(api, tag)

    def test_create_rejects_a_malformed_postal_code_without_echoing_it(
        self, api: AlmaSpeiApi, donor_profile: DonorProfile, tag: str
    ):
        # 1. Submit a donor with a postal code outside the XX-XXX format
        # 2. Verification: HTTP 400 "invalid" on postal-code, value not echoed, nothing stored
        payload = donor_profile.with_changes(postal_code=INVALID_POSTAL_CODE).to_payload()
        response = donors_steps.request_create(api, payload)
        with soft_assertions():
            assert_donor_validation_error(response, "postal-code", FieldErrorCode.INVALID)
            assert_that(response.text).described_as(
                "a validation error should not echo the rejected value"
            ).does_not_contain(INVALID_POSTAL_CODE)
        assert_nothing_stored(api, tag)

    @pytest.mark.parametrize("field", ["is-active", "created-by", "version"])
    def test_create_rejects_server_managed_fields(
        self, api: AlmaSpeiApi, donor_profile: DonorProfile, tag: str, field: str
    ):
        # 1. Submit a donor that also sets a server-managed field
        # 2. Verification: HTTP 400 unknown-field, and nothing is stored
        payload = {**donor_profile.to_payload(), field: SERVER_FIELD_VALUES[field]}
        response = donors_steps.request_create(api, payload)
        assert_donor_validation_error(response, "", FieldErrorCode.UNKNOWN_FIELD)
        assert_nothing_stored(api, tag)


@allure.feature("Donor profiles")
class TestDonorCard(BaseApiTest):
    def test_card_shows_the_profile_and_an_empty_payment_history(
        self, api: AlmaSpeiApi, donor: dict[str, Any]
    ):
        # 1. Open the card of a donor without payments
        # 2. Verification: HTTP 200, the stored donor, no donations and a zero total
        response = donors_steps.get_donor(api, donor["id"])
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "opening a donor card")
            assert_that(body["donor"]).described_as("card should show the donor").is_equal_to(donor)
            assert_that(body["donations"]).described_as("card should list no donations").is_empty()
            assert_that(body["donations-total"]).described_as(
                "card should report zero donations"
            ).is_equal_to(0)

    @pytest.mark.parametrize(
        "donor_id",
        [
            pytest.param(str(uuid.uuid4()), id="unknown-uuid"),
            pytest.param(MALFORMED_DONOR_ID, id="malformed-id"),
        ],
    )
    def test_missing_donor_is_not_found(self, api: AlmaSpeiApi, donor_id: str):
        # 1. Open the card and the history of a donor id that does not exist
        # 2. Verification: both answer HTTP 404 donor not-found
        card = donors_steps.get_donor(api, donor_id)
        history = donors_steps.get_history(api, donor_id)
        with soft_assertions():
            assert_error(card, HTTPStatus.NOT_FOUND, ApiErrorPayload.DONOR_NOT_FOUND)
            assert_error(history, HTTPStatus.NOT_FOUND, ApiErrorPayload.DONOR_NOT_FOUND)

    def test_anonymous_client_cannot_read_donors(
        self, anonymous_api: AlmaSpeiApi, donor: dict[str, Any]
    ):
        # 1. Open an existing donor's card without signing in
        # 2. Verification: HTTP 401 unauthenticated
        response = donors_steps.get_donor(anonymous_api, donor["id"])
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


@allure.feature("Donor profiles")
class TestDonorUpdate(BaseApiTest):
    def test_update_replaces_the_profile_and_bumps_the_version(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Rename the donor and drop its street, sending the current version
        # 2. Verification: HTTP 200, the new name, street cleared (full replacement), version 2
        changed = donor_profile.with_changes(name=donor_profile.name + RENAMED_SUFFIX, street=None)
        response = donors_steps.update_donor(
            api, donor["id"], changed.to_update_payload(donor["version"])
        )
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "updating a donor")
            assert_donor_matches_profile(response.json()["donor"], changed.to_payload())
            assert_that(response.json()["donor"]["version"]).described_as(
                "an effective update should bump the version"
            ).is_equal_to(INITIAL_DONOR_VERSION + 1)

    def test_unchanged_update_keeps_the_version(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Submit the donor's current profile unchanged
        # 2. Read the change history
        # 3. Verification: version stays 1 and only the creation is recorded
        response = donors_steps.update_donor(
            api, donor["id"], donor_profile.to_update_payload(donor["version"])
        )
        history = donors_steps.get_history(api, donor["id"]).json()
        with soft_assertions():
            assert_that(response.json()["donor"]["version"]).described_as(
                "a no-op update should not bump the version"
            ).is_equal_to(INITIAL_DONOR_VERSION)
            assert_that([e["action"] for e in history["events"]]).described_as(
                "a no-op update should not be audited"
            ).is_equal_to([AuditAction.CREATE])

    def test_stale_version_is_rejected(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Update the donor once (version 1 -> 2)
        # 2. Update again still sending version 1
        # 3. Verification: HTTP 409 stale-donor and the first update's name is kept
        first = donor_profile.with_changes(name=donor_profile.name + RENAMED_SUFFIX)
        donors_steps.update_donor(api, donor["id"], first.to_update_payload(donor["version"]))
        response = donors_steps.update_donor(
            api, donor["id"], donor_profile.to_update_payload(donor["version"])
        )
        current = donors_steps.get_donor(api, donor["id"]).json()["donor"]
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ApiErrorPayload.STALE_DONOR)
            assert_that(current["name"]).described_as(
                "a stale update should not overwrite the newer data"
            ).is_equal_to(first.name)


@allure.feature("Donor profiles")
class TestDonorHistory(BaseApiTest):
    def test_history_records_creation_and_field_changes(
        self,
        api: AlmaSpeiApi,
        donor: dict[str, Any],
        donor_profile: DonorProfile,
        settings: Settings,
    ):
        # 1. Rename the donor
        # 2. Read its change history
        # 3. Verification: newest-first update + create events by the admin, with the name diff
        renamed = donor_profile.with_changes(name=donor_profile.name + RENAMED_SUFFIX)
        donors_steps.update_donor(api, donor["id"], renamed.to_update_payload(donor["version"]))
        history = donors_steps.get_history(api, donor["id"]).json()
        update_event = history["events"][0]
        with soft_assertions():
            assert_that(history["total"]).described_as(
                "history should hold two events"
            ).is_equal_to(2)
            assert_that([e["action"] for e in history["events"]]).described_as(
                "history should list the update before the creation"
            ).is_equal_to([AuditAction.UPDATE, AuditAction.CREATE])
            assert_that({e["actor-name"] for e in history["events"]}).described_as(
                "every event should name the administrator as actor"
            ).is_equal_to({settings.admin_display_name})
            assert_that(update_event["changes"]).described_as(
                "the update should record exactly the name change"
            ).is_equal_to([{"field": "name", "before": donor_profile.name, "after": renamed.name}])

    def test_history_is_paginated(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Rename the donor so it has two history events
        # 2. Read the history one event per page, second page
        # 3. Verification: one event (the creation) with the full total
        renamed = donor_profile.with_changes(name=donor_profile.name + RENAMED_SUFFIX)
        donors_steps.update_donor(api, donor["id"], renamed.to_update_payload(donor["version"]))
        page = donors_steps.get_history(api, donor["id"], limit=1, offset=1).json()
        with soft_assertions():
            assert_that([e["action"] for e in page["events"]]).described_as(
                "the second page should hold only the creation"
            ).is_equal_to([AuditAction.CREATE])
            assert_that(page["total"]).described_as("total should count all events").is_equal_to(2)


# --- file-local data and helpers ----------------------------------------------
#: Values for server-managed fields a client must not set.
SERVER_FIELD_VALUES: dict[str, object] = {
    "is-active": False,
    "created-by": str(uuid.uuid4()),
    "version": INITIAL_DONOR_VERSION,
}


def without(payload: dict, key: str) -> dict:
    return {k: v for k, v in payload.items() if k != key}


def assert_nothing_stored(api: AlmaSpeiApi, tag: str):
    assert_that(donors_steps.list_tagged(api, tag, status="all")).described_as(
        "a rejected donor should not be stored"
    ).is_empty()
