# Exploratory sessions 2026-11-28 - Antoni

All sessions ran in Chrome 158 against dev `main` @ a722a1a on a fresh local stack with
the demo data and the dev sample files. Steps were driven through Playwright one at a
time and judged from screenshots, the page text and the accessibility tree. Card titles
are listed in [the run record](2026-11-28-antoni-full.md#cards-filed).

## EXP-01: A first import, as a new staff member

| Field | Value |
| --- | --- |
| Mission | Explore the guided import from the Start screen with the sample files to discover where a first-time user hesitates or misunderstands |
| Time box | Observed during the first imports of the acceptance run, not timed separately |
| Starting point | Fresh demo database, administrator signed in |

**Session notes**

- "Importuj przelewy" on Start leads straight to the upload form. "Jak przygotować plik?" explains the four columns, the date formats and quoting clearly.
- "Ustawienia źródła — raz dla całego pliku" is understandable. The note under it explains that the type only affects new profiles.
- Typing the currency by hand ("np. PLN") works but is unusual. Later the exception form asks for it again.
- Every screen says that nothing is saved before approval ("Baza darczyńców i wpłat nie została jeszcze zmieniona."). This is clear.
- The step indicator shows step 3 "Dopasowanie" on a summary with exceptions and step 4 "Podsumowanie" on a ready one, while both screens are headed "Podsumowanie importu".

**Problems found**

| # | What happened | Expected | Severity | Card |
| --- | --- | --- | --- | --- |
| 1 | Step indicator and heading disagree | One name for the screen | Low | UX: formats and texts |
| 2 | Currency asked again in the exception form | Prefilled with the file's currency | Low | UX: exceptions |

## EXP-02: Explaining exceptions, the hard way

| Field | Value |
| --- | --- |
| Mission | Explore exception resolution with an invented file (two transfers from one new person, one non-exact "Jan Kowalski") and the demo donors to discover lost drafts, confusing choices and dead ends |
| Time box | About 30 minutes |
| Starting point | Batch staged with "Nie wiem" as the type of new donors |

**Session notes**

- Without a type, new senders become exceptions ("Nowy darczyńca wymaga określenia typu…"). "Dodaj nowego darczyńcę" prefills the name, street, postcode and city from the sender.
- Leaving a half-filled new-donor form through the sidebar asks "Opuścić bieżący wiersz i odrzucić niezapisany szkic?". The draft is gone afterwards, as announced.
- The browser Back button from an exception leaves the batch for the Start screen; Forward returns to the summary.
- The second transfer from the same new person says "Brak podobnych aktywnych profili"; "Użyj nowego darczyńcy przygotowanego w tym imporcie" lists the prepared profile and works.
- Choosing the wrong "Jan Kowalski" and then "Zmień darczyńcę" works; "Wróć do podsumowania" is disabled meanwhile without a reason.
- Searching inside the exception finds "Wiśn" and "kowal" but not "wisn", a street or a city. The status filter there also reaches archived profiles.
- After the three explanations the summary is ready (1 matched, 1 new donor, 3 new payments).

**Problems found**

| # | What happened | Expected | Severity | Card |
| --- | --- | --- | --- | --- |
| 1 | The prepared new donor is not suggested for the second transfer | Suggested like an existing profile | Medium | UX: exceptions |
| 2 | No search without Polish letters or by address | Both work | Medium | UX: exceptions |
| 3 | "Wróć do podsumowania" disabled without explanation | A reason or an enabled button with a draft warning | Low | UX: exceptions |
| 4 | Back leaves the batch | Back returns to the summary | Low | UX: navigation |

## EXP-03: Interruptions and failures

| Field | Value |
| --- | --- |
| Mission | Explore what the user sees when the session or the network fails mid-task |
| Time box | About 25 minutes |
| Starting point | Several batches in review |

**Session notes**

- Signing out in a second tab: the first tab's next action shows "Sesja wygasła. Zaloguj się ponownie." with "Odśwież sesję", which leads to the sign-in form. After signing in again the user returns to the same import summary (the deep link is kept).
- Going offline during "Prześlij i dopasuj automatycznie" shows "Nie udało się potwierdzić wyniku przesyłania. Plik mógł zostać zapisany. Nie przesyłamy go ponownie automatycznie." with only "Wybierz inny plik". Back online, choosing the same file again uploads it normally.
- After a failed analysis (wrong columns) the form switches to "Ponów analizę tego samego pliku". A corrected file is refused by the server, and "Nowy import" in the sidebar does not reset the form.
- Not run: stopping the backend during an upload or a commit, and waiting out the idle session limit.

**Problems found**

| # | What happened | Expected | Severity | Card |
| --- | --- | --- | --- | --- |
| 1 | A corrected file after a failed analysis is refused | It can be uploaded as a new import | Medium | Bug: retry |
| 2 | The offline message does not say what to do | A link to the import history | Low | UX: exceptions |
| 3 | The workspace stays visible after the session ended | Straight to sign-in, or an explicit message | Low | UX: accounts |

## EXP-04: The donor register with odd data

| Field | Value |
| --- | --- |
| Mission | Explore the register with unusual synthetic profiles to discover layout and search problems |
| Time box | About 15 minutes |
| Starting point | Demo profiles, edited in place |

**Session notes**

- A name "=SUMA(A1:A9)" is stored and shown as plain text everywhere.
- "O'Connor-Woźniak Emilia" and a long street with brackets save and display correctly.
- A name of more than 200 characters wraps cleanly on the card, in the list and in the history; the page never scrolls sideways. The name field has no length limit in the browser.
- Every edit adds an "Edycja profilu" entry with the old and new values.
- Clicking "Darczyńcy" in the sidebar while on a card does nothing.

**Problems found**

| # | What happened | Expected | Severity | Card |
| --- | --- | --- | --- | --- |
| 1 | The active sidebar item does not return to the list | It opens the list | Low | UX: navigation |

## EXP-05: Accounts and permissions as staff

| Field | Value |
| --- | --- |
| Mission | Explore the app as a staff member without account management to discover anything shown or allowed that should not be |
| Time box | About 15 minutes |
| Starting point | A new staff account created by the administrator |

**Session notes**

- The staff menu has no "Konta użytkowników". Guessed addresses for an accounts screen open the Start screen.
- Import deep links (`#review/…`, `#imports/history/0`, `#imports/batch/…`) open for staff, which matches the role: staff work on imports.
- `GET /api/accounts` as staff answers 403 with "Brak uprawnień do zarządzania kontami."
- Changing one's own password works and the new password signs in, but there is no confirmation message.

**Problems found**

| # | What happened | Expected | Severity | Card |
| --- | --- | --- | --- | --- |
| 1 | No confirmation after changing one's own password | A short success message | Low | UX: accounts |
