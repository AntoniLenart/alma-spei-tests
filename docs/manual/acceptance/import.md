# Acceptance scenarios: bank import

Preconditions for every case:

- signed in as the synthetic administrator;
- the backend started with `ALMA_SYNTHETIC_IMPORTS=true`, so the labelled test commit is available;
- demo data seeded on a fresh database.

Files come from the dev repository's `docs/testing-samples/`. Do not upload the
CSV and the XLSX of `bank-valid` into the same database, because they hold the
same invented transfers.

## MAN-I-01: A valid CSV is matched automatically and ready to approve

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_upload.py`, `tests/api/test_bank_matching.py`. The manual run checks clarity. |

**Steps**

1. Choose "Nowy import" and pick `bank-valid.csv`.
2. Choose the separator "Średnik (;)", type `PLN` as the currency, and choose "Osoby" as the type of new donors.
3. Choose "Prześlij i dopasuj automatycznie".

**Expected result**

- The import summary opens with "Dopasowane przelewy" 2, "Nowi darczyńcy" 1, "Nowe wpłaty" 3 and "Do wyjaśnienia" 0, and "Do dodania: 250,00 PLN".
- Jan Kowalski is matched to the profile at ul. Słoneczna 1/4, 32-020 Wieliczka; Jakub Nowak stays a separate donor; Helena Nowicka is prepared as a new donor.
- "Wszystko gotowe do zatwierdzenia" is offered. Nothing has changed in the donor register yet.

## MAN-I-02: The XLSX variant needs no separator

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_upload.py` (XLSX). Use a fresh database. |

**Steps**

1. Choose "Nowy import" and pick `bank-valid.xlsx`.
2. Confirm `PLN` and submit.

**Expected result**

- No separator choice is offered.
- The summary matches MAN-I-01, and the physical worksheet rows 1–3 are kept.

## MAN-I-03: The same file again is refused, even renamed

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_upload.py`, `tests/api/test_bank_upload.py`. |

**Steps**

1. After MAN-I-01, upload `bank-valid.csv` again under another name (copy and rename it first).

**Expected result**

- The alert reads "Ten plik został już przesłany, także jeśli wcześniej miał inną nazwę. Kolejny import nie został utworzony.", with "Otwórz historię importów".

## MAN-I-04: Invalid rows stay visible with Polish reasons

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_review.py`, `tests/api/test_import_negative_catalogue.py`. |

**Steps**

1. Upload `bank-invalid-rows.csv` (";", `PLN`).
2. In the summary, choose "Wyjaśnij tę pozycję" for the invalid row.

**Expected result**

- One row is listed as "Błędy w danych źródłowych — popraw plik."
- Beside it, the source card lists the invalid date, the missing sender and the invalid amount in Polish, and warns that choosing a donor does not fix the file.
- Approval is not offered.

## MAN-I-05: A negative amount is explained and blocks approval

| Field | Value |
| --- | --- |
| Automation | Candidate for an e2e test (covered by API tests). |

**Steps**

1. Upload `bank-negative.csv` (";", `PLN`).
2. Explain the negative row.

**Expected result**

- The row is an exception ("Kwota ujemna wymaga wyjaśnienia zasad zwrotów.").
- Its panel says that approval is blocked until the refund rules are settled.

## MAN-I-06: A file with the wrong columns is refused as a whole

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/api/test_import_negative_catalogue.py` (five columns). |

**Steps**

1. Upload `bank-wrong-columns.csv` (";", `PLN`).

**Expected result**

- A Polish structural error is shown on the upload screen, and no summary opens.
- The donor register is unchanged.

## MAN-I-07: Ambiguous transfers need a person, and only those

| Field | Value |
| --- | --- |
| Automation | Partly covered by `tests/api/test_bank_matching.py`. The full flow is a candidate for e2e. |

**Steps**

1. Upload `bank-ambiguities.csv` (";", `PLN`, "Osoby").
2. Read the exceptions. Explain the non-exact "Jan Kowalski" and choose the right profile after comparing the addresses ("To ten darczyńca").
3. In "2. Sprawdź wpłatę", type the confirmed currency, describe how it was checked, choose "Nowa, odrębna wpłata", tick the check for an earlier inclusion and choose "Zapisz wyjaśnienie i wróć do podsumowania".
4. Explain each repeated "Jakub Nowak" payment the same way and decide whether it is a separate payment.

**Expected result**

- Exactly three exceptions are listed; the remaining transfer is prepared automatically.
- The candidates show their address and a Polish reason. Choosing one only prepares a draft: the payment is saved only after the currency, the justification, the way to record it and the overlap check are given. The form lists what is still missing.
- After saving, the summary opens again with one exception fewer.
- A possible duplicate always needs an explicit decision: the same date and amount alone never count as a duplicate.
- "Wpłata jest już ujęta w bazie" asks for a payment that is already in the database. A twin row of the same file cannot be chosen there (see the run of 2026-11-28 and its bug card).

## MAN-I-08: The review queue reopens a batch with its settings

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_review.py`. |

**Steps**

1. Leave a batch with exceptions, choose "Do weryfikacji", and open it from "Importy do dokończenia".
2. Reload the browser page.

**Expected result**

- The batch shows its progress ("Sprawdzone przelewy: …").
- It reopens on its summary without asking for the currency again, and the reload keeps the state.

## MAN-I-09: The change plan and the explicit test commit

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_execution.py`. The manual run checks the wording of the confirmation. |

**Steps**

1. From a ready summary, choose "Sprawdź zmiany i zatwierdź".
2. Read the planned changes, then choose "Przygotuj zatwierdzenie testowe".
3. Tick the consent and choose "Zatwierdź import testowy".

**Expected result**

- The confirmation "Zatwierdź sprawdzone przelewy" lists every planned change and states that existing profiles keep their fields.
- It warns that no real backup is made.
- Committing is impossible before the receipt and the consent. Afterwards, the outcome shows the saved commit, its author and the PLN total.

## MAN-I-10: History and outcome

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_execution.py`. |

**Steps**

1. Choose "Historia importów" and find the committed file.
2. Open "Szczegóły pliku i przebiegu", then "Zobacz wynik importu".

**Expected result**

- The entry shows the state "Zapisany", the upload date and the uploader, with the metadata in the details.
- The outcome shows the commit.
- A batch still under review offers "Kontynuuj sprawdzanie przelewów" instead.

## MAN-I-11: Undoing the latest import

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_execution.py`, `tests/api/test_import_undo.py`. |

**Steps**

1. On the outcome of the latest commit, choose "Cofnij ostatni import", then "Anuluj cofnięcie".
2. Choose "Cofnij ostatni import" again, then "Potwierdzam cofnięcie importu".
3. Look for Helena Nowicka in "Darczyńcy".

**Expected result**

- Cancelling changes nothing.
- Confirming shows "Import został cofnięty", with the reversed payments and archived profiles counted, and the history kept.
- The donor created by the import is archived and gone from the default list. An older import offers no undo.

## MAN-I-12: Re-importing an undone file is a new attempt

| Field | Value |
| --- | --- |
| Automation | Covered by `tests/e2e/test_import_execution.py`. |

**Steps**

1. On the undone outcome, choose "Wczytaj ten sam plik ponownie".
2. Choose the same file and separator, type `PLN`, tick the confirmation and retry.

**Expected result**

- A new batch (attempt 2) opens on its summary.
- The undone attempt stays in the history.
