"""Page object for the donor list.

Mirrors src/ui/alma_spei/ui/donors/views.cljs. The list renders inside the
auth panel once the "Darczyńcy" screen is selected.
"""

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage


class DonorMessages:
    """Exact Polish strings of the donor screens."""

    LIST_HEADING = "Darczyńcy"
    SEARCH_BUTTON = "Szukaj"
    CLEAR_FILTERS = "Wyczyść filtry"
    TABLE_REGION = "Tabela darczyńców"
    EMPTY = "Brak darczyńców spełniających wybrane warunki."
    OPEN_CARD_PREFIX = "Otwórz kartę: "
    ACTIVE = "Aktywny"
    ARCHIVED = "Archiwalny"
    #: entity-type -> table label (labels.cljs ``entity-types``)
    ENTITY_LABELS = {"individual": "Osoba", "business": "Firma", "organization": "Organizacja"}

    @staticmethod
    def results_summary(first: int, last: int, total: int) -> str:
        return f"Wyniki: {first}–{last} z {total}"


class DonorListPage(BasePage):
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=DonorMessages.LIST_HEADING, exact=True)

    @property
    def search_input(self) -> Locator:
        return self.page.locator("#donor-search")

    @property
    def entity_type_select(self) -> Locator:
        return self.page.locator("#donor-type")

    @property
    def status_select(self) -> Locator:
        return self.page.locator("#donor-status")

    @property
    def table(self) -> Locator:
        return self.page.get_by_role("region", name=DonorMessages.TABLE_REGION)

    @property
    def rows(self) -> Locator:
        return self.table.locator("tr.donor-row")

    @property
    def empty_message(self) -> Locator:
        return self.table.get_by_text(DonorMessages.EMPTY, exact=True)

    @property
    def results_summary(self) -> Locator:
        return self.page.locator('nav.donor-pagination [role="status"]')

    def row(self, name: str) -> Locator:
        return self.rows.filter(has=self.open_card_button(name))

    def open_card_button(self, name: str) -> Locator:
        return self.page.get_by_role(
            "button", name=f"{DonorMessages.OPEN_CARD_PREFIX}{name}", exact=True
        )

    def row_cells(self, name: str) -> list[str]:
        return [text.strip() for text in self.row(name).locator("td").all_inner_texts()]

    def search(self, text: str):
        self.search_input.fill(text)
        self.page.get_by_role("button", name=DonorMessages.SEARCH_BUTTON).click()

    def filter_by_type(self, entity_type: str):
        self.entity_type_select.select_option(entity_type)

    def filter_by_status(self, status: str):
        self.status_select.select_option(status)
