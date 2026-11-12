"""Page objects for the donor list and the donor card.

Mirrors src/ui/alma_spei/ui/donors/views.cljs (list) and detail_views.cljs
(card). Both render inside the auth panel once the "Darczyńcy" screen is
selected; the card replaces the list when a donor is opened.
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

    #: Profile field labels on the card (labels.cljs ``fields``).
    CITY_FIELD = "Miejscowość"

    BACK_TO_LIST = "Wróć do listy"
    EDIT = "Edytuj dane"
    SAVE = "Zapisz zmiany"
    CANCEL_EDIT = "Anuluj edycję"
    SAVED = "Zapisano zmiany."
    NO_PAYMENTS = "Brak wpłat dla tego darczyńcy."
    HISTORY_HEADING = "Historia zmian profilu"
    #: audit action -> history heading (labels.cljs ``actions``)
    ACTION_LABELS = {"create": "Utworzenie profilu", "update": "Edycja profilu"}

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

    def open_card(self, name: str):
        self.open_card_button(name).click()


class DonorCardPage(BasePage):
    @property
    def heading(self) -> Locator:
        return self.page.locator("#donor-detail-heading")

    @property
    def edit_button(self) -> Locator:
        return self.page.get_by_role("button", name=DonorMessages.EDIT)

    @property
    def save_button(self) -> Locator:
        return self.page.get_by_role("button", name=DonorMessages.SAVE)

    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name=DonorMessages.BACK_TO_LIST)

    @property
    def saved_notice(self) -> Locator:
        return self.page.get_by_text(DonorMessages.SAVED, exact=True)

    @property
    def no_payments(self) -> Locator:
        return self.page.get_by_text(DonorMessages.NO_PAYMENTS, exact=True)

    @property
    def history_section(self) -> Locator:
        return self.page.locator("section").filter(
            has=self.page.get_by_role("heading", name=DonorMessages.HISTORY_HEADING)
        )

    @property
    def history_entries(self) -> Locator:
        return self.history_section.locator("article h4")

    def edit_field(self, field: str) -> Locator:
        """The edit-form input for a kebab-case field, e.g. ``"name"``."""
        return self.page.locator(f"#donor-edit-{field}")

    def field_error(self, field: str) -> Locator:
        return self.page.locator(f"#donor-edit-{field}-error")

    def profile_value(self, label: str) -> Locator:
        """The <dd> shown for a profile field label (labels.cljs ``fields``)."""
        return (
            self.page.locator("dl.donor-profile > div")
            .filter(has=self.page.locator("dt", has_text=label))
            .locator("dd")
        )

    def start_editing(self):
        self.edit_button.click()

    def set_field(self, field: str, value: str):
        self.edit_field(field).fill(value)

    def save(self):
        self.save_button.click()
