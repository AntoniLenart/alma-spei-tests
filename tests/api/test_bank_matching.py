"""API tests for the deterministic 100%-certainty bank matching (task 60).

The matching only reads senders written as ``name, street, NN-NNN city``. It
links a row to a donor only when that normalized identity (name, street, postal
code, city) equals exactly one active profile. The same name at another address,
another person at the same address, an archived profile or two identical
profiles are never guessed between: the row is left for a person, with the
candidates. Spelling variants the normalization knows (case, spacing, "ulica" /
"ul.") still match; a missing diacritic is a different identity.
"""

from http import HTTPStatus
from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    MATCHING_RULE_VERSION,
    OTHER_CURRENCY,
    DecisionKind,
    EntityType,
    ExceptionReason,
    ReconciliationErrorPayload,
)
from alma_spei_tests.data import (
    DonorFactory,
    existing_donor,
    new_donor_profile,
    sender_of,
    sender_with_address,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps, review_steps
from alma_spei_tests.testbase import BaseApiTest

#: The policy a person confirms for these files: PLN, new donors are individuals.
INDIVIDUALS = review_steps.policy(new_donor_type=EntityType.INDIVIDUAL)
#: The same currency, but no type for new donors (they cannot be proposed).
NO_NEW_DONORS = review_steps.policy()

#: A street, postal code and city no test donor uses.
ELSEWHERE = ("ul. Nieznana 99", "00-950", "Innowo")


@allure.feature("Bank matching")
class TestExactMatches(BaseApiTest):
    def test_a_full_identity_match_links_the_payment_to_the_donor(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row whose sender is exactly the donor's name and address
        # 2. Reconcile it
        # 3. Verification: one match, no exception, the batch ready; the row is a complete
        #    decision for that donor
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor)])
        response = review_steps.reconcile(api, batch_id, INDIVIDUALS)
        body = response.json()
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "reconciling a batch")
            assert_that(
                (body["counts"]["matched"], body["counts"]["exceptions"], body["ready"])
            ).described_as("the row should be matched automatically").is_equal_to((1, 0, True))
            assert_that(
                (decision["kind"], decision["donor-id"], decision["complete"])
            ).described_as("the decision should link the donor").is_equal_to(
                (DecisionKind.EXISTING_DONOR, donor["id"], True)
            )

    def test_the_automatic_decision_records_its_rule(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage and reconcile an exact match
        # 2. Read the review history
        # 3. Verification: the saved decision names the matching rule version
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor)])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        events = review_steps.read_review_events(api, batch_id).json()["events"]
        rules = [e["after"].get("automation", {}).get("rule-version") for e in events]
        assert_that(rules).described_as(
            "the automatic decision should record the matching rule"
        ).contains(MATCHING_RULE_VERSION)

    def test_case_spacing_and_street_prefix_variants_still_match(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create a donor on "ul. Akacjowa 7"
        # 2. Stage a row with the name and city in capitals, extra spaces and "ulica Akacjowa 7"
        # 3. Reconcile it
        # 4. Verification: still matched to that donor
        donor = donor_factory(new_donor_profile(tag=tag).with_changes(street="ul. Akacjowa 7"))
        sender = sender_with_address(
            f"  {donor['name'].upper()}  ",
            "ulica  Akacjowa 7",
            donor["postal-code"],
            donor["city"].upper(),
        )
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        assert_that(decision and decision["donor-id"]).described_as(
            "known spelling variants should not stop an exact match"
        ).is_equal_to(donor["id"])


@allure.feature("Bank matching")
class TestNoGuessing(BaseApiTest):
    def test_the_same_name_at_another_address_is_never_linked(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row with the donor's name but another address
        # 2. Reconcile it
        # 3. Verification: left for a person as an identity ambiguity, with the donor as a
        #    candidate, and no link saved
        batch_id = imports_steps.stage_senders(
            api, tag, [sender_with_address(donor["name"], *ELSEWHERE)]
        )
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.IDENTITY_AMBIGUITY, [donor])

    def test_another_person_at_the_same_address_is_never_linked(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row with another name at the donor's address (a household member)
        # 2. Reconcile it
        # 3. Verification: left for a person, with the donor as a candidate
        sender = sender_with_address(
            f"Inny Domownik {tag}", donor["street"], donor["postal-code"], donor["city"]
        )
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.IDENTITY_AMBIGUITY, [donor])

    def test_a_missing_diacritic_is_another_identity(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create "Anna Wiśniewska" at some address
        # 2. Stage a row from "Anna Wisniewska" at that address
        # 3. Reconcile it
        # 4. Verification: not matched - left for a person with the donor as a candidate
        donor = donor_factory(
            new_donor_profile(tag=tag).with_changes(name=f"Anna Wiśniewska {tag}")
        )
        sender = sender_with_address(
            f"Anna Wisniewska {tag}", donor["street"], donor["postal-code"], donor["city"]
        )
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.IDENTITY_AMBIGUITY, [donor])

    def test_two_identical_profiles_are_never_guessed_between(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create two donors with the same name and address
        # 2. Stage a row from that identity and reconcile it
        # 3. Verification: left for a person, with both donors as candidates
        profile = new_donor_profile(tag=tag)
        twins = [donor_factory(profile), donor_factory(profile)]
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(twins[0])])
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.IDENTITY_AMBIGUITY, twins)

    def test_an_archived_exact_match_is_not_linked(
        self, api: AlmaSpeiApi, db: DbQueries, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create a donor and archive it
        # 2. Stage a row with exactly its identity and reconcile it
        # 3. Verification: left for a person; only active profiles are suggested (task 61), so
        #    the archived donor is not offered
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(archived)])
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.IDENTITY_AMBIGUITY, [])

    def test_a_sender_without_an_address_is_left_for_a_person(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row whose sender is only the donor's name
        # 2. Reconcile it
        # 3. Verification: left for a person because the sender layout cannot be read
        batch_id = imports_steps.stage_senders(api, tag, [donor["name"]])
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.SENDER_FORMAT, [])


@allure.feature("Bank matching")
class TestNewDonors(BaseApiTest):
    def test_an_unknown_sender_becomes_a_proposal_under_an_individual_policy(
        self, api: AlmaSpeiApi, tag: str
    ):
        # 1. Stage a row from a full identity nobody in the register shares
        # 2. Reconcile it, with new donors confirmed as individuals
        # 3. Verification: the row is linked to a new proposal with exactly the parsed identity
        profile = new_donor_profile(tag=tag)
        sender = sender_with_address(profile.name, *address_of(profile))
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        proposals = review_steps.list_proposals(api, batch_id).json()["proposals"]
        with soft_assertions():
            assert_that(decision and decision["kind"]).described_as(
                "an unknown sender should get a proposal"
            ).is_equal_to(DecisionKind.NEW_PROPOSAL)
            assert_that([identity_of(p["profile"]) for p in proposals]).described_as(
                "the proposal should carry the parsed identity only"
            ).is_equal_to([(profile.name, *address_of(profile))])

    def test_without_a_new_donor_type_an_unknown_sender_waits(self, api: AlmaSpeiApi, tag: str):
        # 1. Stage a row from an unknown full identity
        # 2. Reconcile it without a type for new donors
        # 3. Verification: left for a person - the type is never guessed
        profile = new_donor_profile(tag=tag)
        batch_id = imports_steps.stage_senders(
            api, tag, [sender_with_address(profile.name, *address_of(profile))]
        )
        body = review_steps.reconcile(api, batch_id, NO_NEW_DONORS).json()
        assert_left_for_a_person(api, batch_id, body, ExceptionReason.DONOR_TYPE, [])


@allure.feature("Bank matching")
class TestReconciliationGuards(BaseApiTest):
    def test_a_manual_decision_is_not_overwritten(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_factory: DonorFactory, tag: str
    ):
        # 1. Stage an exact match for one donor, but link the row to another donor by hand
        # 2. Reconcile the batch
        # 3. Verification: the manual decision is kept
        other = donor_factory(new_donor_profile(tag=tag))
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor)])
        review_steps.decide(api, batch_id, 1, existing_donor(other))
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        assert_that(decision["donor-id"]).described_as(
            "the automatic matching should never overwrite a person's decision"
        ).is_equal_to(other["id"])

    def test_reconciling_again_changes_nothing(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage and reconcile an exact match
        # 2. Reconcile it again under the same policy
        # 3. Verification: the batch version did not move
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor)])
        first = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        again = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        assert_that(again["batch"]["version"]).described_as(
            "a repeated reconciliation should be a no-op"
        ).is_equal_to(first["batch"]["version"])

    def test_another_policy_is_refused_once_one_is_confirmed(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage and reconcile a batch in PLN
        # 2. Reconcile it again in another currency
        # 3. Verification: 409 policy-conflict
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor)])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        response = review_steps.reconcile(
            api, batch_id, review_steps.policy(OTHER_CURRENCY, EntityType.INDIVIDUAL)
        )
        assert_error_includes(
            response, HTTPStatus.CONFLICT, ReconciliationErrorPayload.POLICY_CONFLICT
        )


# --- file-local helpers -------------------------------------------------------
def address_of(profile: Any) -> tuple[str, str, str]:
    return (profile.street, profile.postal_code, profile.city)


def identity_of(profile: dict[str, Any]) -> tuple[str, str, str, str]:
    return (profile["name"], profile["street"], profile["postal-code"], profile["city"])


def assert_left_for_a_person(
    api: AlmaSpeiApi,
    batch_id: str,
    body: dict[str, Any],
    reason: str,
    candidates: list[dict[str, Any]],
):
    """Row 1 is an exception with ``reason`` and exactly these candidates, and is not linked."""
    exceptions = [e for e in body["exceptions"] if e["row"]["row-number"] == 1]
    decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
    with soft_assertions():
        assert_that([e["reason"] for e in exceptions]).described_as(
            f"row 1 should be left for a person as {reason}"
        ).is_equal_to([reason])
        assert_that(sorted(c["id"] for e in exceptions for c in e["candidates"])).described_as(
            "the exception should offer exactly the related donors"
        ).is_equal_to(sorted(c["id"] for c in candidates))
        assert_that(decision is None or decision["kind"] == DecisionKind.UNRESOLVED).described_as(
            "no link should be saved for an ambiguous row"
        ).is_true()
