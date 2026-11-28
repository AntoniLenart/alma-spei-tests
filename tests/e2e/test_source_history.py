"""E2E tests for master and tax imports in the import history (task 67).

Master and tax uploads are staged only: they have no bank review or outcome
yet, so their history entries show the file, the state and the details, but
offer neither "Kontynuuj sprawdzanie przelewów" nor "Zobacz wynik importu".
"""

import allure
import pytest
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ImportSource
from alma_spei_tests.data.sources import MasterRow, TaxRow, TaxSubject, master_csv, tax_csv
from alma_spei_tests.pages import ExecutionMessages
from alma_spei_tests.steps import imports_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest


@allure.feature("Import history UI")
class TestSourceHistory(BaseE2ETest):
    @pytest.mark.parametrize("source", [ImportSource.MASTER, ImportSource.TAX])
    def test_a_staged_master_or_tax_import_offers_no_bank_actions(
        self, signed_in_page: Page, api: AlmaSpeiApi, tag: str, source: str
    ):
        # 1. Stage a master or tax file through the API
        # 2. Open the import history from the navigation
        # 3. Verification: the entry is listed as awaiting review, with its details, but
        #    without the bank review or outcome links
        filename = f"{tag}-{source}.csv"
        content = (
            master_csv([MasterRow(name=f"Jan Historia {tag}")])
            if source == ImportSource.MASTER
            else tax_csv([TaxRow("1", TaxSubject("Jan", f"Historia {tag}"))])
        )
        imports_steps.upload_staged(api, filename, content, source=source)
        execution = ui_steps.open_history(signed_in_page)
        entry = execution.history_entry(filename)
        expect(execution.state_badge(entry)).to_have_text(ExecutionMessages.STATE_REVIEW)
        expect(entry.get_by_role("link")).to_have_count(0)
        execution.open_entry_details(entry)
        expect(execution.context_value(ExecutionMessages.FILE, entry)).to_have_text(filename)
