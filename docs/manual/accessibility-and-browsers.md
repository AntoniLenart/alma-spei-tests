# Accessibility and browsers

Go through this checklist once per run and per browser for the main flows: sign-in,
the donor list and card, and an import from upload to undo. Record a line per item
in the run record. Every **Fail** gets a card.

## Keyboard only

| ID | Check | Automation |
| --- | --- | --- |
| ACC-01 | Every action can be reached with Tab and Shift+Tab and triggered with Enter or Space, with no mouse | Manual only |
| ACC-02 | The skip link is the first stop and moves to the content | Covered by `tests/e2e/test_app_shell.py` |
| ACC-03 | The focus order follows the visual order on every screen, including the side-by-side exception panel | Manual only |
| ACC-04 | The focus is always visible (outline or equivalent), also on custom buttons and filter toggles | Manual only |
| ACC-05 | After a screen change (upload → summary, summary → exception), the focus lands on the new heading | Candidate |
| ACC-06 | No keyboard trap: the file picker, selects and the menu toggle can be left with Tab or Escape | Manual only |

## Dialogs and confirmations

| ID | Check | Automation |
| --- | --- | --- |
| ACC-07 | The undo dialog takes the focus, keeps it inside, closes with Escape or "Anuluj cofnięcie", and returns the focus to "Cofnij ostatni import" | Candidate |
| ACC-08 | Browser confirmations (password reset, unsaved draft) say clearly what will happen | Manual only |

## Screen reader (NVDA on Windows, or VoiceOver)

| ID | Check | Automation |
| --- | --- | --- |
| ACC-09 | Landmarks are announced: "Nawigacja główna", the main content, the regions such as "Tabela darczyńców" | Manual only |
| ACC-10 | Status messages ("Zapisano zmiany.", upload progress, matching progress) are announced without moving the focus | Manual only |
| ACC-11 | Errors are announced and tied to their fields (an invalid currency, a refused password) | Manual only |
| ACC-12 | Filter toggles announce their pressed state ("Do wyjaśnienia (n)", "Dopasowane w 100% (n)") | Manual only |

## Narrow screen (about 390 px)

| ID | Check | Automation |
| --- | --- | --- |
| ACC-13 | The menu folds behind "Menu" and opens and closes | Covered by `tests/e2e/test_workspace.py` |
| ACC-14 | No horizontal scrolling on any screen; tables and the side-by-side panel stack readably | Manual only |
| ACC-15 | Buttons and links are large enough to tap; nothing important is cut off | Manual only |
| ACC-16 | Zoom to 200 % on desktop gives the same results as the narrow screen | Manual only |

## Browser matrix

Run the acceptance scenarios marked with a browser focus, MAN-D-01 to MAN-D-05
and MAN-I-01, MAN-I-04, MAN-I-09 and MAN-I-11, in each browser. Run the rest at least in Chrome.

| Browser | Version (record it) | Notes |
| --- | --- | --- |
| Chrome | current stable | The automated e2e suite runs in Chromium |
| Firefox | current stable | Check the file picker, the date display and the focus outlines |
| Edge | current stable | Check the downloads/upload behaviour and the saved-password prompts |
