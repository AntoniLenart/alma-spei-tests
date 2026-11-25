# Exploratory session charters: the new interface

Each charter is one time-boxed session. Copy the
[session template](../templates/session-charter.md) into the run folder, fill in
the notes and the problems, and link the cards you file.

## EXP-01: A first import, as a new staff member

| Field | Value |
| --- | --- |
| Mission | Explore the guided import from the Start screen with the sample files to discover where a first-time user hesitates or misunderstands |
| Time box | 45 minutes |
| Area | Start screen, "Importuj przelewy", upload form, import summary, confirmation |

**Ideas to try**

- Read only the screen, not the dev guide.
  - Is it clear what "Ustawienia źródła — raz dla całego pliku" means and why the currency must be typed?
  - Is the type of new donors explained clearly enough?
- Follow the step indicator ("Plik → Sprawdzenie danych → Dopasowanie → Podsumowanie → Zatwierdzenie"). Does it match where you are?
- Can you tell at every moment that nothing is saved yet?

## EXP-02: Explaining exceptions, the hard way

| Field | Value |
| --- | --- |
| Mission | Explore exception resolution with `bank-ambiguities.csv` and the demo donors to discover lost drafts, confusing choices and dead ends |
| Time box | 60 minutes |
| Area | "Wyjaśnij tę pozycję", donor search and comparison, new donor form, payment question, "Wróć do podsumowania" |

**Ideas to try**

- Start an explanation and leave halfway: use the sidebar, the browser back button, a reload, a second tab.
- Choose the wrong donor, then correct it ("Zmień darczyńcę").
- Prepare a new donor, then reuse it for a second transfer ("Użyj nowego darczyńcy przygotowanego w tym imporcie").
- Search with Polish letters, partial names and the address.

## EXP-03: Interruptions and failures

| Field | Value |
| --- | --- |
| Mission | Explore what the user sees when the session, the network or the backend fails mid-task |
| Time box | 45 minutes |
| Area | Every screen, especially upload, commit and undo |

**Ideas to try**

- Sign out in another tab, then continue.
- Wait out the idle session limit.
- Stop the backend during an upload or a commit, then start it again.
- Switch the browser offline during "Prześlij i dopasuj automatycznie".
- Check whether every message says what happened and what to do, in Polish, without technical details.

## EXP-04: The donor register at scale and with odd data

| Field | Value |
| --- | --- |
| Mission | Explore the register with many and unusual synthetic profiles to discover layout and search problems |
| Time box | 30 minutes |
| Area | Donor list, card, edit form |

**Ideas to try**

- Use very long names and addresses, Polish letters, apostrophes and hyphens.
- Use names that look like formulas (`=SUMA(…)`).
- Page through and sort many results.
- Edit back and forth and read the history.

## EXP-05: Accounts and permissions as staff

| Field | Value |
| --- | --- |
| Mission | Explore the app as a staff member without account management to discover anything shown or allowed that should not be |
| Time box | 30 minutes |
| Area | Sidebar, deep links (`#review/…`, `#imports/…`), account panel |

**Ideas to try**

- Open the administrator's deep links as staff.
- Try the account panel's address directly.
- Reset your own password, then sign in again.
