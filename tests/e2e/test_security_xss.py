"""E2E security tests for stored cross-site scripting (XSS).

Text that people or bank files supply - a donor's name, an import's file name,
a transfer's sender - is shown on several screens. Each probe tries to run
script that sets a flag on ``window``; the screens must show the text as text
and the flag must stay unset.
"""

import datetime as dt
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.data import BankRow, BankStatement, DonorFactory, new_donor_profile
from alma_spei_tests.steps import imports_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: The window property a successful injection would set.
FLAG = "__almaXss"
#: Markup probes (no double quotes, so they also survive as multipart file names).
PROBES = (
    f"<img src=x onerror=window.{FLAG}=1>",
    f"<svg onload=window.{FLAG}=1>",
    f"</strong><script>window.{FLAG}=1</script>",
)


#: Escaped markup in a file name: it must stay as written, never decoded into a tag.
ENTITY_NAME = "&lt;img src=x onerror=alert(1)&gt;"


@allure.feature("Security: XSS")
class TestStoredXss(BaseE2ETest):
    @pytest.mark.parametrize("probe", PROBES, ids=["img-onerror", "svg-onload", "script-tag"])
    def test_a_donor_name_is_shown_as_text(
        self, signed_in_page: Page, donor_factory: DonorFactory, tag: str, probe: str
    ):
        # 1. Create a donor whose name is a script probe
        # 2. Find it in the donor list and open its card
        # 3. Verification: the name is shown literally on both screens, and no script ran
        donor = donor_factory(new_donor_profile(tag=tag).with_changes(name=f"{probe} {tag}"))
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        ui_steps.wait_for_row_count(donors, 1)
        ui_steps.open_donor_card(donors, donor["name"])
        assert_no_script_ran(signed_in_page)

    @pytest.mark.parametrize("name", [PROBES[0], ENTITY_NAME], ids=["markup-name", "entity-name"])
    def test_an_import_file_name_and_sender_are_shown_as_text(
        self, signed_in_page: Page, api: AlmaSpeiApi, tag: str, name: str
    ):
        # 1. Stage a statement whose sender is a script probe and whose file name holds
        #    markup or HTML entities
        # 2. Open it from the review queue, run the matching and explain its row
        # 3. Open the import history
        # 4. Verification: the file name and sender are shown literally, and no script ran
        filename = f"{name}{tag}.csv"
        sender = f"{PROBES[1]} {tag}"
        row = BankRow(dt.date(2026, 1, 15), sender, f"Darowizna {tag}", "10,00")
        response = imports_steps.upload(api, filename, BankStatement([row]).to_csv())
        if response.status_code == HTTPStatus.BAD_REQUEST:
            pytest.skip("this platform's form reader refuses the name (Windows); nothing to show")
        batch = response.json()["batch"]
        review = ui_steps.open_review_queue(signed_in_page)
        expect(review.queue_item(filename)).to_be_visible()
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], filename)
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, sender)
        expect(review.source_card).to_contain_text(sender)
        history = ui_steps.open_history(signed_in_page)
        expect(history.history_entry(filename)).to_be_visible()
        assert_no_script_ran(signed_in_page)


# --- file-local helpers -------------------------------------------------------
def assert_no_script_ran(page: Page):
    assert_that(page.evaluate(f"() => window.{FLAG} === undefined")).described_as(
        "no injected script should have run"
    ).is_true()
