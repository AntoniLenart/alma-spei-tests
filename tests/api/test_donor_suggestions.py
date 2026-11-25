"""API tests for the donor suggestions of the bank matching (task 61).

For a row without a 100% match, the reconciliation report suggests up to five
active profiles, ranked by the evidence they share with the sender: the exact
identity, then the accent-folded full name together with the full address, the
name alone, the address alone, and the last name token of an individual. Each
suggestion carries its Polish reason. A similar profile holds back the automatic
proposal of a new donor; a row like nobody in the register is flagged as a
candidate for a new profile. Suggestions follow the current catalogue and never
replace a person's decision.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    MAX_SUGGESTIONS,
    DecisionKind,
    EntityType,
    ExceptionReason,
    MatchReason,
)
from alma_spei_tests.data import (
    DonorFactory,
    DonorProfile,
    existing_donor,
    new_donor_profile,
    sender_of,
    sender_with_address,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps, review_steps
from alma_spei_tests.testbase import BaseApiTest

#: New donors in these files are individuals, so an unknown sender could be proposed.
INDIVIDUALS = review_steps.policy(new_donor_type=EntityType.INDIVIDUAL)
#: No type for new donors.
NO_NEW_DONORS = review_steps.policy()


@allure.feature("Donor suggestions")
class TestSuggestionRanking(BaseApiTest):
    def test_each_kind_of_similarity_is_ranked_and_explained(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create, around one sender's identity, a donor with the name spelled without
        #    diacritics at the same address, a namesake elsewhere, a neighbour at the same
        #    address, and someone else sharing only the last name
        # 2. Stage a row from that sender and reconcile it
        # 3. Verification: an identity ambiguity, not a new donor; the four donors are
        #    suggested strongest first, each with its Polish reason
        sender = new_donor_profile(tag=tag).with_changes(name=f"Łucja Żółkiewska {tag}")
        expected = [
            (
                donor_factory(sender.with_changes(name=f"Lucja Zolkiewska {tag}")),
                MatchReason.NAME_AND_ADDRESS,
            ),
            (donor_factory(elsewhere(sender, tag, name=sender.name)), MatchReason.NAME),
            (
                donor_factory(sender.with_changes(name=f"Inna Sąsiadka {tag}-obok")),
                MatchReason.ADDRESS,
            ),
            (
                donor_factory(elsewhere(sender, tag, name=f"Bogumił Daleki {tag}")),
                MatchReason.LAST_NAME,
            ),
        ]
        batch_id = imports_steps.stage_senders(api, tag, [sender_line(sender)])
        row = first_exception(review_steps.reconcile(api, batch_id, INDIVIDUALS).json())
        with soft_assertions():
            assert_that((row["reason"], row["new-profile-candidate"])).described_as(
                "a similar profile should leave the row for a person, not for a new donor"
            ).is_equal_to((ExceptionReason.IDENTITY_AMBIGUITY, False))
            assert_that(suggested(row)).described_as(
                "the suggestions should be ranked by their evidence, each with its reason"
            ).is_equal_to([(donor["id"], reason) for donor, reason in expected])

    def test_two_identical_profiles_are_suggested_as_exact(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create two donors with the same identity
        # 2. Stage a row from that identity and reconcile it
        # 3. Verification: both are suggested as an exact name and address
        profile = new_donor_profile(tag=tag)
        twins = [donor_factory(profile), donor_factory(profile)]
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(twins[0])])
        row = first_exception(review_steps.reconcile(api, batch_id, INDIVIDUALS).json())
        assert_that(sorted(suggested(row))).described_as(
            "both identical profiles should be suggested as exact"
        ).is_equal_to(sorted((twin["id"], MatchReason.EXACT) for twin in twins))

    def test_at_most_five_profiles_are_suggested(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create one more namesake than the suggestion limit, each at its own address
        # 2. Stage a row from that name at yet another address and reconcile it
        # 3. Verification: five namesakes are suggested
        name = f"Jadwiga Liczna {tag}"
        profile = new_donor_profile(tag=tag)
        for number in range(MAX_SUGGESTIONS + 1):
            donor_factory(elsewhere(profile, f"{tag}-{number}", name=name))
        sender = elsewhere(profile, f"{tag}-wplata", name=name)
        batch_id = imports_steps.stage_senders(api, tag, [sender_line(sender)])
        row = first_exception(review_steps.reconcile(api, batch_id, INDIVIDUALS).json())
        assert_that([reason for _, reason in suggested(row)]).described_as(
            "no more than five namesakes should be suggested"
        ).is_equal_to([MatchReason.NAME] * MAX_SUGGESTIONS)


@allure.feature("Donor suggestions")
class TestNewProfileCandidates(BaseApiTest):
    def test_a_sender_like_nobody_is_a_new_profile_candidate(self, api: AlmaSpeiApi, tag: str):
        # 1. Stage a row from an identity nobody in the register resembles
        # 2. Reconcile it without a type for new donors
        # 3. Verification: no suggestions, and the row is flagged as a new profile candidate
        sender = new_donor_profile(tag=tag)
        batch_id = imports_steps.stage_senders(api, tag, [sender_line(sender)])
        row = first_exception(review_steps.reconcile(api, batch_id, NO_NEW_DONORS).json())
        assert_that((row["reason"], row["new-profile-candidate"], row["candidates"])).described_as(
            "a sender like nobody should be offered as a new profile"
        ).is_equal_to((ExceptionReason.DONOR_TYPE, True, []))

    def test_a_similar_profile_holds_back_an_automatic_new_donor(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create a donor who shares only the last name with the sender
        # 2. Stage the row and reconcile it with new donors confirmed as individuals
        # 3. Verification: no proposal is prepared; the row waits with that donor suggested
        sender = new_donor_profile(tag=tag)
        relative = donor_factory(elsewhere(sender, tag, name=f"Krewny Odległy {tag}"))
        batch_id = imports_steps.stage_senders(api, tag, [sender_line(sender)])
        row = first_exception(review_steps.reconcile(api, batch_id, INDIVIDUALS).json())
        proposals = review_steps.list_proposals(api, batch_id).json()["proposals"]
        with soft_assertions():
            assert_that((row["reason"], suggested(row))).described_as(
                "a resemblance should be shown to a person"
            ).is_equal_to(
                (ExceptionReason.IDENTITY_AMBIGUITY, [(relative["id"], MatchReason.LAST_NAME)])
            )
            assert_that(proposals).described_as(
                "no new donor should be prepared while a similar profile exists"
            ).is_empty()


@allure.feature("Donor suggestions")
class TestSuggestionsFollowTheCatalogue(BaseApiTest):
    def test_an_archived_profile_drops_out_of_the_suggestions(
        self, api: AlmaSpeiApi, db: DbQueries, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row from the donor's name at another address and reconcile it
        # 2. Archive the donor, then read the report again
        # 3. Verification: the catalogue revision moved on and the donor is no longer suggested
        sender = sender_with_address(donor["name"], *elsewhere_address(tag))
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        before = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        db_steps.archive_donor(db, donor["id"])
        after = review_steps.read_reconciliation(api, batch_id).json()
        with soft_assertions():
            assert_that(suggested(first_exception(before))).described_as(
                "the active namesake should be suggested first"
            ).is_equal_to([(donor["id"], MatchReason.NAME)])
            assert_that(after["catalog-version"]).described_as(
                "archiving should move the catalogue revision on"
            ).is_greater_than(before["catalog-version"])
            assert_that(first_exception(after)["candidates"]).described_as(
                "an archived profile should no longer be suggested"
            ).is_empty()

    def test_a_suggestion_never_replaces_a_manual_decision(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_factory: DonorFactory, tag: str
    ):
        # 1. Stage a row from the donor's name at another address
        # 2. Link the row to another donor by hand, then reconcile
        # 3. Verification: the manual decision is kept and the row is no exception
        other = donor_factory(new_donor_profile(tag=tag))
        sender = sender_with_address(donor["name"], *elsewhere_address(tag))
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review_steps.decide(api, batch_id, 1, existing_donor(other))
        body = review_steps.reconcile(api, batch_id, INDIVIDUALS).json()
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        with soft_assertions():
            assert_that((decision["kind"], decision["donor-id"])).described_as(
                "the person's choice should be kept"
            ).is_equal_to((DecisionKind.EXISTING_DONOR, other["id"]))
            assert_that(body["exceptions"]).described_as(
                "a decided row should not be suggested again"
            ).is_empty()


# --- file-local helpers -------------------------------------------------------
def sender_line(profile: DonorProfile) -> str:
    return sender_with_address(
        profile.name, profile.street or "", profile.postal_code or "", profile.city
    )


def elsewhere_address(seed: str) -> tuple[str, str, str]:
    """A street, postal code and city no other donor uses."""
    return (f"ul. Odległa {seed}", "00-950", "Innowo")


def elsewhere(profile: DonorProfile, seed: str, *, name: str) -> DonorProfile:
    """``profile`` renamed to ``name`` and moved to an address of its own."""
    street, postal_code, city = elsewhere_address(seed)
    return profile.with_changes(name=name, street=street, postal_code=postal_code, city=city)


def first_exception(body: dict[str, Any]) -> dict[str, Any]:
    rows = [e for e in body["exceptions"] if e["row"]["row-number"] == 1]
    assert_that(rows).described_as("row 1 should be left for a person").is_length(1)
    return rows[0]


def suggested(row: dict[str, Any]) -> list[tuple[str, str]]:
    """The suggested donors of an exception, in order, with their reasons."""
    return [(c["id"], c["match-reason"]) for c in row["candidates"]]
