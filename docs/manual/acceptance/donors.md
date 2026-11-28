# Acceptance scenarios: donor register

Preconditions for every case: signed in as the synthetic administrator, with the fictional demo
data seeded on a fresh database. The demo data has 20 profiles, 18 of them active,
including two "Jan Kowalski" at different addresses.

## MAN-D-01: The list shows the active donors, paged

| Field | Value |
| --- | --- |
| PBI | Donor register |
| Automation | Covered by `tests/e2e/test_donors.py`, `tests/api/test_donor_list.py`. The manual run checks the wording and layout. |

**Steps**

1. Choose "Darczyńcy" in the sidebar.
2. Look at the table, the summary under it and the paging controls.

**Expected result**

- The heading is "Darczyńcy", with a "Tabela darczyńców" table of active profiles only.
- Each row shows the name, type ("Osoba", "Firma", "Organizacja"), city and status "Aktywny".
- The summary reads "Wyniki: 1–N z 18" and paging is offered when there are more rows than fit.

## MAN-D-02: Search finds names case-insensitively and literally

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/api/test_donor_list.py`. The manual run checks the Polish letters and the empty state. |

**Steps**

1. Search for "kowalski", then "KOWALSKI", then "Wiśniewska", then "%", then "zzz".
2. Choose "Wyczyść filtry".

**Expected result**

- Both "Jan Kowalski" profiles are found in either letter case; "Wiśniewska" finds Anna Wiśniewska.
- "%" and "zzz" show "Brak darczyńców spełniających wybrane warunki."
- "Wyczyść filtry" restores the full list.

## MAN-D-03: Status and type filters and sorting

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_donors.py` (status). Type and sort are candidates for automation. |

**Steps**

1. Set the status filter to archived, then to all.
2. Set the type filter to "Firma".
3. Sort by city, descending.

**Expected result**

- Archived shows the 2 archived profiles marked "Archiwalny"; all shows 20.
- "Firma" shows the 4 businesses only.
- The order follows the city, Polish letters sorted sensibly, with no duplicate or missing rows across pages.

## MAN-D-04: The donor card shows the profile, payments and history

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_donors.py`. The manual run checks readability. |

**Steps**

1. Open the card of one "Jan Kowalski" ("Otwórz kartę: Jan Kowalski").
2. Read the profile fields, the payments and "Historia zmian profilu".
3. Choose "Wróć do listy".

**Expected result**

- The card shows the address and city, the payments with dates and PLN amounts (comma decimals), and the history entry "Utworzenie profilu".
- The other "Jan Kowalski" is a separate card with another address. The two are never merged.
- "Wróć do listy" returns to the same list position and filters.

## MAN-D-05: Editing a donor saves, validates and is audited

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_donors.py`, `tests/api/test_donor_profiles.py`. The manual run checks the messages. |

**Steps**

1. On a card choose "Edytuj dane" and change the city, then "Zapisz zmiany".
2. Edit again, clear the name and try to save.
3. Edit again, then "Anuluj edycję".

**Expected result**

- After saving, "Zapisano zmiany." is shown and the history gains "Edycja profilu" with the old and new city.
- An empty name is refused with a clear Polish message next to the field, and nothing is saved.
- Cancelling restores the saved values.

## MAN-D-06: A concurrent edit is not overwritten silently

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/api/test_donor_profiles.py` (version conflict). Manual only for the screen message. |

**Steps**

1. Open the same card in two browser tabs and choose "Edytuj dane" in both.
2. Save a change in the first tab, then save another change in the second.

**Expected result**

- The second save is refused with a Polish message that the data changed, offering to reload. The first change is kept.
