# Manual tests

Manual testing covers what the automated suite cannot judge:

- whether the screens are usable and the Polish wording is clear;
- accessibility with a keyboard and a screen reader;
- narrow screens;
- behaviour in each supported browser.

Everything runs against **dev `main` on a local, disposable stack with synthetic
data only**. Never use real donor data, real bank statements or real accounts.

## Contents

| Folder / file | What |
| --- | --- |
| [`templates/`](templates/) | Templates for a test case, an exploratory session charter and an execution record |
| [`acceptance/`](acceptance/) | Acceptance scenarios of the finished PBIs, each with steps and the expected result |
| [`exploratory/`](exploratory/) | Charters for exploratory sessions of the new interface |
| [`accessibility-and-browsers.md`](accessibility-and-browsers.md) | Keyboard, focus, dialogs, screen reader, 390 px and the browser matrix |
| [`polish-texts.md`](polish-texts.md) | Review checklist for the Polish wording |
| [`runs/`](runs/) | One execution record per run, with the date, the app version and the results |

## Setting up a run

1. Check out dev `main` and note the commit (`git rev-parse --short HEAD`). It is
   the **app version** of the record.
2. Start a fresh, disposable stack as in the dev README:
   - run `bb init`, `bb db-up`, `bb migrate` and `bb create-admin` with a synthetic username;
   - start the backend with `ALMA_SYNTHETIC_IMPORTS=true bb repl`, which enables only the labelled test commit;
   - in a second terminal, run `bb ui`.
3. Seed the fictional demo data with `bb seed-demo <admin-username>`. Several
   scenarios rely on its two "Jan Kowalski" profiles and on "Jakub Nowak".
4. Use the synthetic sample files from the dev repository's
   `docs/testing-samples/`:
   - `bank-valid.csv` and `bank-valid.xlsx`;
   - `bank-invalid-rows.csv`, `bank-negative.csv` and `bank-wrong-columns.csv`;
   - `bank-ambiguities.csv`.
5. Copy [`templates/execution-record.md`](templates/execution-record.md) to
   `runs/<date>-<tester>-<scope>.md` and fill it in as you go.

The stack is disposable. Some scenarios commit and undo imports, so start from a
fresh database whenever a scenario says "fresh demo database".

## Recording results

- Every executed scenario or session gets a line in the run's record: **Pass**,
  **Fail**, **Blocked** or **Not run**, with a short note.
- A **Fail** gets either a bug card on the board (`[Bug][...]`, with the steps,
  the expected and actual result and a severity) or, for wording or usability
  points, a UX note card for dev. The record links the card.
- Screenshots may only show synthetic data.

## Automation candidates

Every scenario says how it relates to the automated suite:

- **Covered by `<test>`**: the steps are already automated. The manual run is
  about wording and usability.
- **Candidate**: worth automating. When a candidate is automated, the scenario
  names the test.
- **Manual only**: judgement, accessibility or browser behaviour.
