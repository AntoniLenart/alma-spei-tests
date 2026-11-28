# Polish wording review

Read every screen, message and button of the main flows and note any problem as
a UX note card for dev. Quote the exact text and the screen.

| ID | Check |
| --- | --- |
| TXT-01 | No typos, missing diacritics or broken encodings ("Zażółć" must never show as "ZaĹĽĂłĹ‚Ä‡") |
| TXT-02 | One name per thing across the app: "import" / "plik", "przelew" / "wpłata", "darczyńca" / "profil" are used consistently and as intended |
| TXT-03 | Buttons say what they do ("Prześlij i dopasuj automatycznie", "Zatwierdź import testowy") and match the confirmation that follows |
| TXT-04 | Error messages say what happened and what to do next, with no codes or technical words (no "batch", "payload", "500") |
| TXT-05 | Test-only features are clearly labelled as such ("Wersja testowa · dane fikcyjne", "zatwierdzenie testowe") and never suggest a real backup |
| TXT-06 | Numbers, dates and amounts use the Polish format (comma decimals, `PLN` after the amount, day-month-year where shown to people) |
| TXT-07 | Gendered forms are handled ("Zatwierdził(a)", "Przesłał(a)") or rephrased neutrally |
| TXT-08 | Empty states ("Brak darczyńców spełniających wybrane warunki.", "Brak automatycznych dopasowań w 100%.") are helpful and not alarming |

Known points to look at first:

- the step indicator labels compared with the screen headings;
- the reason texts of the exceptions;
- the warnings about synthetic data on the confirmation.
