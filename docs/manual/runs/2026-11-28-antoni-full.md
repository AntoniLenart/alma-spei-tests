# Manual run 2026-11-28 - Antoni - full

| Field | Value |
| --- | --- |
| Date | 2026-11-28 |
| Tester | Antoni |
| App version | dev `main` @ a722a1a |
| Stack | local, fresh database for each browser, demo data seeded: yes, synthetic imports: on |
| Browser(s) | Chrome 158, Firefox 157 (Playwright build), Edge 158 |
| Screen sizes | desktop 1366 × 900; 390 px; 683 px wide as the 200 % zoom equivalent |
| Method | Every step was carried out in a real browser through Playwright, one step at a time, and each screen was judged from screenshots, the page text and the accessibility tree. No screen reader was used. |

Four disposable stacks were used: Chrome (all scenarios, sessions and checks),
Firefox and Edge (the browser-focus scenarios), and one more fresh database for
the XLSX variant, which must not share a database with the CSV of the same
transfers. Only the dev sample files and invented data were used.

## Cards filed

| Kind | Card title on the board |
| --- | --- |
| Bug, medium | [Bug][Frontend] Po nieudanej analizie pliku formularz przyjmuje tylko „ten sam plik” – poprawiony plik jest odrzucany |
| Bug, medium, to decide | [Bug][Backend] Powtórzonego przelewu z tego samego pliku nie da się oznaczyć jako duplikatu – do decyzji |
| Bug, low/medium, to decide | [Bug][Backend] Po cofnięciu i ponownym wczytaniu importu darczyńca zarchiwizowany przez cofnięcie nie jest pokazany – ryzyko duplikatu profilu |
| UX | [UX][Frontend] Formaty kwot i dat oraz teksty techniczne w interfejsie |
| UX | [UX][Frontend] Nawigacja: przycisk Wstecz, aktywna pozycja menu i menu na wąskim ekranie |
| UX | [UX][Frontend] Wyjaśnianie wyjątków importu – usprawnienia |
| UX | [UX][Frontend] Logowanie i konta użytkowników – komunikaty i etykiety |

In the tables below, "Bug: retry", "Bug: in-file duplicate", "Bug: archived after
undo", "UX: formats and texts", "UX: navigation", "UX: exceptions" and "UX:
accounts" refer to these cards.

## Results: acceptance scenarios

| Case | Chrome | Firefox | Edge | Note | Card |
| --- | --- | --- | --- | --- | --- |
| MAN-A-01 | Pass | | | Only the Polish "Logowanie" form, no navigation, no self-registration. | |
| MAN-A-02 | Pass | | | The temporary password leads to "Zmiana hasła". A deep link stays blocked until the change. A weak password gets "Nowe hasło nie spełnia wymagań." and the policy hint; under 8 characters the browser's own length message blocks the form. | UX: accounts |
| MAN-A-03 | Pass | | | The reset confirmation says the sessions end. The staff window's next action shows "Sesja wygasła. Zaloguj się ponownie." and no data, but the menu and "Zalogowano jako" stay until "Odśwież sesję". A deactivated account gets the generic sign-in refusal. | UX: accounts |
| MAN-D-01 | Pass | Pass | Pass | 18 active profiles, "Wyniki: 1–18 z 18". The table is named "Lista darczyńców" inside the "Tabela darczyńców" region. | |
| MAN-D-02 | Pass | Pass | Pass | Case-insensitive, literal "%". "wisniewska" without Polish letters finds nothing. | UX: exceptions |
| MAN-D-03 | Pass | Pass | Pass | Archived 2, all 20, firms 4, city sort both ways. Rows within one city have no secondary order. | |
| MAN-D-04 | Pass | Pass | Pass | "Wróć do listy" keeps the filters and the sort. Amounts show four decimals ("10,0000"). The browser Back button leaves the app. | UX: formats and texts, UX: navigation |
| MAN-D-05 | Pass | Pass | Pass | "Zapisano zmiany." and an "Edycja profilu" entry. An empty or blank name shows "Podaj nazwę lub imię i nazwisko darczyńcy." (tied to the field) and disables saving. | |
| MAN-D-06 | Pass | | | The second tab gets a clear conflict message and "Wczytaj aktualne dane"; it says "przez inną osobę" although it was the same person. | UX: formats and texts |
| MAN-I-01 | Pass | Pass | Pass | 2 / 1 / 3 / 0 and "Do dodania: 250,00 PLN"; the register is unchanged before approval. | |
| MAN-I-02 | Pass | | | No separator choice; the same summary; worksheet rows 1–3. | |
| MAN-I-03 | Pass | | | A renamed copy gets the exact duplicate message and "Otwórz historię importów". | |
| MAN-I-04 | Pass | Pass | Pass | The three Polish reasons and the warning are shown and approval is not offered, but the panel still offers a donor choice. The invalid row's card reads "· 0 PLN" with no title. | UX: exceptions |
| MAN-I-05 | Pass | | | "Kwota ujemna wymaga wyjaśnienia zasad zwrotów." and approval blocked. The row shows "Waluta: Nieustalona" although PLN was set for the file. | UX: formats and texts |
| MAN-I-06 | Pass | | | A Polish structural error and no summary. The message mentions formulas for a CSV. Choosing the next file afterwards hits the retry bug. | Bug: retry |
| MAN-I-07 | Pass | | | Exactly three exceptions. The expected result was out of date: since the review filters change a donor choice only prepares a draft and the payment form must be completed (now updated in `acceptance/import.md`). The twin "Jakub Nowak" row cannot be marked as already included. | Bug: in-file duplicate |
| MAN-I-08 | Pass | | | The queue shows the progress; the batch reopens on its summary without the currency question; a reload keeps it. | |
| MAN-I-09 | Pass | Pass | Pass | Committing needs the receipt and the consent; the warning about no real backup is shown; the outcome shows the author and the PLN total. Plan and outcome show UUIDs and the algorithm name; the outcome still says "Nowy proponowany darczyńca". | UX: formats and texts |
| MAN-I-10 | Pass | | | "Zapisany", date and uploader, details complete; a batch under review offers "Kontynuuj sprawdzanie przelewów". A failed analysis's outcome gives no reason and shows a disabled undo section. | UX: exceptions |
| MAN-I-11 | Pass | Pass | Pass | Cancel changes nothing; the confirmation counts 3 reversed payments and 1 archived profile; Helena Nowicka is archived. "An older import offers no undo" was not exercised (only one commit existed). | |
| MAN-I-12 | Pass | | | A new batch opens and the undone attempt stays as "Cofnięty". The donor archived by the undo becomes an exception with no candidate. | Bug: archived after undo |

## Results: exploratory sessions

Session notes are in [2026-11-28-antoni-exploratory.md](2026-11-28-antoni-exploratory.md).

| Session | Result | Note | Card |
| --- | --- | --- | --- |
| EXP-01 | Done | Observed during the first imports; no separate time box. | UX: formats and texts |
| EXP-02 | Done | Drafts, wrong donor and correction, reused new donor, searches. | UX: exceptions, UX: navigation |
| EXP-03 | Partly | Sign-out in another tab and offline upload done. Stopping the backend and the idle session limit were not run. | Bug: retry, UX: exceptions |
| EXP-04 | Done | Formula-like, apostrophe, hyphen and very long values. No problems. | |
| EXP-05 | Done | Staff see imports but no account management; the accounts API answers 403 in Polish. | UX: accounts |

## Results: accessibility and browsers

| ID | Result | Note | Card |
| --- | --- | --- | --- |
| ACC-01 | Pass | Start, donor list, card, edit and the import flow work with Tab, Enter and arrow keys. | |
| ACC-02 | Pass | First stop after a load; moves the focus to the content. | |
| ACC-03 | Pass | The order follows the layout: sidebar, filters, sort buttons, rows; the exception panel reads left (file row) then right (decision). | |
| ACC-04 | Pass | A visible ring everywhere checked (3 px solid in all three browsers). The ring of the search field overlaps its label. | UX: navigation |
| ACC-05 | Pass | After each screen change the focus lands on the new H2 (list, card, confirmation) or H3 (exception). | |
| ACC-06 | Pass | No trap in the selects or the menu. The native file dialog itself was not opened. | |
| ACC-07 | Pass | Native modal dialog; the focus starts on "Anuluj cofnięcie", stays inside, Escape closes and the focus returns to "Cofnij ostatni import" (all three browsers). | |
| ACC-08 | Pass | The reset, deactivation and leave-the-draft confirmations say what happens; the last one has a technical second sentence. | UX: formats and texts |
| ACC-09 | Not run | No screen reader. The accessibility tree has "Nawigacja główna", main and named regions. | |
| ACC-10 | Not run | No screen reader. Status messages use `status` roles; the review queue gives every item its own `status`, which may be noisy. | |
| ACC-11 | Not run | No screen reader. The name error is an `alert` tied to the field with `aria-describedby`; account fields repeat the same names. | UX: accounts |
| ACC-12 | Not run | No screen reader. The filter toggles expose `aria-pressed`. | |
| ACC-13 | Pass | The menu folds behind "Menu" and opens, but stays open after choosing a destination. | UX: navigation |
| ACC-14 | Pass | No page-level horizontal scrolling on any screen. The donor and payment tables scroll inside their region, with a hint. | UX: navigation |
| ACC-15 | Pass | Only the 18 × 18 px checkboxes are small, and their labels are clickable. | |
| ACC-16 | Pass | Same as the narrow screen at 683 px wide (viewport, not browser zoom). | |

The browser-focus scenarios passed in all three browsers with no console errors,
except a 404 for the missing favicon in Edge.

## Results: Polish texts

| ID | Result | Note | Card |
| --- | --- | --- | --- |
| TXT-01 | Pass | No broken diacritics anywhere. | |
| TXT-02 | Fail | "Aktywny: Aktywny" vs "Tak"; two different session-ended messages; "Odśwież analizę" vs "Odśwież automatyczne dopasowania"; "Arkusz 1" for a CSV; heading "Podsumowanie importu" while the step indicator shows "Dopasowanie". | UX: formats and texts |
| TXT-03 | Pass | Buttons match their confirmations. "Sprawdź wynik importu" on the confirmation before committing is unclear. | |
| TXT-04 | Fail | UUIDs and "bank-exact-identity-v2" are shown to staff. | UX: formats and texts |
| TXT-05 | Pass | "Wersja testowa · dane fikcyjne" and the test-commit warnings never suggest a real backup. | |
| TXT-06 | Fail | Four-decimal amounts in three places; ISO dates on import screens, DD.MM.RRRR in the register. | UX: formats and texts |
| TXT-07 | Fail | "Zatwierdził(a)" and "Przesłał(a)" next to "Cofnął/cofnęła". | UX: formats and texts |
| TXT-08 | Pass | Empty states are short and calm. | |

## Summary

- Acceptance scenario runs: 39 passed (21 in Chrome, 9 in Firefox, 9 in Edge), 0 failed, 0 blocked.
- Exploratory sessions: 4 done, 1 partly (backend stop and idle limit not run).
- Accessibility: 12 passed, 4 not run (screen reader).
- Polish texts: 4 passed, 4 failed (all on one UX card).
- New cards: 3 bug cards and 4 UX cards, listed above.
- The MAN-I-07 expected result was updated to the draft-then-confirm flow.
- Automation candidates noticed:
  - choosing another file after a failed analysis (once the retry bug is fixed);
  - the in-file duplicate and the archived-after-undo cases, once decided;
  - the concurrent edit message on screen (MAN-D-06);
  - the focus moving to the new heading after a screen change (ACC-05);
  - the undo dialog's focus and Escape handling (ACC-07);
  - no page-level horizontal scrolling at 390 px (ACC-14), using `scrollWidth`.
- Still to do in a later run: a screen reader pass (NVDA) for ACC-09 to ACC-12, the backend-stop and idle-limit parts of EXP-03, and the branded Firefox build.
