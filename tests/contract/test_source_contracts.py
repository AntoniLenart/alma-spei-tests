"""Contract tests for the master and tax import responses (tasks 65-67).

The upload and rows responses dispatch on the batch's source: master rows carry
the profile fields and source observations, tax rows the taxpayer, the spouse,
the purpose and the amount (``contracts.imports.SOURCE_*_RESPONSE``).
"""

import allure
import pytest
from assertpy import soft_assertions

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ImportSource
from alma_spei_tests.contracts import SOURCE_ROWS_RESPONSE, SOURCE_UPLOAD_RESPONSE
from alma_spei_tests.data.sources import MasterRow, TaxRow, TaxSubject, master_csv, tax_csv
from alma_spei_tests.steps import imports_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Master and tax import contract")
class TestSourceContracts(BaseContractTest):
    @pytest.mark.parametrize("source", [ImportSource.MASTER, ImportSource.TAX])
    def test_upload_and_rows_responses_match_their_source_contract(
        self, api: AlmaSpeiApi, tag: str, source: str
    ):
        # 1. Stage a master or tax file with a valid and an invalid row
        # 2. Read its rows
        # 3. Verification: both bodies satisfy the source's contract
        if source == ImportSource.MASTER:
            content = master_csv([MasterRow(name=f"Jan {tag}"), MasterRow(name="", extra="x")])
        else:
            content = tax_csv(
                [TaxRow("1", TaxSubject("Jan", f"Kontrakt {tag}")), TaxRow("2", amount="abc")]
            )
        upload = imports_steps.upload_staged(api, f"{tag}.csv", content, source=source)
        rows = imports_steps.read_rows(api, upload["batch"]["id"]).json()
        with soft_assertions():
            assert_matches_contract(upload, SOURCE_UPLOAD_RESPONSE[source], f"{source} upload")
            assert_matches_contract(rows, SOURCE_ROWS_RESPONSE[source], f"{source} rows")
