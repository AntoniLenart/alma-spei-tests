# Negative import cases: damaged and unusual bank files

A bank file can be broken in endless ways. For every damaged file the import
must:

- never answer with a server error (5xx);
- never lose a line silently, and never invent one;
- never accept wrong data as valid;
- never write to the donor or payment tables before an import is approved.

Two layers check this against the bank adapter (`date;sender;description;amount`,
no header, CSV with `;` or `,`, or a single-sheet XLSX).

| Layer | Where | What |
| --- | --- | --- |
| Catalogue | `tests/api/test_import_negative_catalogue.py` | One test per case below, with its exact expected outcome. |
| Generated files | `tests/api/test_import_generated_corruptions.py` | Valid statements damaged at random from a fixed seed (`data.corrupt.generated_corruptions`): nasty field values, missing or extra columns, blank lines, quotes, embedded newlines, other line endings and encodings, flipped bytes, truncation. Every file must keep the invariants above. |

The generator is plain `random.Random` with a seed, so a failing file can be
replayed. The regression run uploads 40 files from seed `20261125`. For a longer
exploratory run, set:

```sh
ALMA_TEST_CORRUPTION_SEED=7 ALMA_TEST_CORRUPTION_COUNT=300 uv run pytest -n0 tests/api/test_import_generated_corruptions.py
```

The test id names the damage, for example
`017-drop-column+flipped-byte`. Setting the same seed and count rebuilds the
same files.

## Outcomes

- **Staged** — 201. Every non-empty line is a row: valid, or invalid with its
  Polish reasons (`invalid-date`, `missing-sender`, `invalid-amount`). Blank
  lines are skipped and counted.
- **Refused** — the whole file is rejected with a Polish message, and the
  reserved batch is marked failed:
  - `400 parse-failed` and `400 invalid-structure` answer "Nieprawidłowy format pliku importu.";
  - `400 unsupported-format` answers the same message;
  - `413 resource-limit` answers "Plik przekracza limit importu.".

## Catalogue

Case ids are the pytest ids. **Rows** lists `row: reasons`, where `ok` means
the row is valid.

### Encoding

| Case | File | Expected |
| --- | --- | --- |
| `utf8-with-bom` | UTF-8 with a byte-order mark | Staged, `1: ok, 2: ok` (the BOM is not part of the first date) |
| `utf16` | UTF-16 | Refused, 400 parse-failed |
| `windows-1250-polish` | Windows-1250 with Polish letters | Refused, 400 parse-failed (no garbled names) |
| `iso-8859-2-polish` | ISO-8859-2 with Polish letters | Refused, 400 parse-failed |
| `windows-1250-ascii-only` | Windows-1250 without Polish letters (identical to ASCII) | Staged, `1: ok` |
| `invalid-utf8-sequence` | A broken UTF-8 sequence in a name | Refused, 400 parse-failed |
| `mixed-encodings` | One UTF-8 line, one Windows-1250 line | Refused, 400 parse-failed (nothing half-staged) |

### Structure

| Case | File | Expected |
| --- | --- | --- |
| `three-columns` | A line without the amount | Staged, `1: invalid-amount` |
| `five-columns` | A line with an extra column | Refused, 400 invalid-structure |
| `ragged-rows` | One full line, one without the amount | Staged, `1: ok, 2: invalid-amount` |
| `header-row` | A header line `Data;Nadawca;Opis;Kwota` | Staged, `1: invalid-date, invalid-amount` (the header is visible, not hidden), `2: ok, 3: ok` |
| `blank-and-whitespace-lines` | An empty and a spaces-only line between rows | Staged, `1: ok, 4: ok`, 2 skipped (physical line numbers kept) |
| `no-trailing-newline` | The last line without a newline | Staged, `1: ok, 2: ok` |
| `crlf-line-endings` | CRLF | Staged, `1: ok, 2: ok` |
| `crlf-without-final-newline` | CRLF, last line without one | Staged, `1: ok, 2: ok` |
| `cr-line-endings` | CR only (old Mac) | Staged, `1: ok, 2: ok`. **Known bug:** the final CR adds a phantom invalid row (`strict xfail`). |
| `mixed-line-endings` | CRLF, LF and a final CR | Staged, three valid rows. **Same known bug.** |

### Separators

| Case | File | Expected |
| --- | --- | --- |
| `commas-read-with-semicolon` | Comma-separated content, `;` chosen | Staged, `1: invalid-date, missing-sender, invalid-amount` (one-cell line, nothing guessed) |
| `mixed-separators` | One `;` line and one `,` line | Staged, `1: ok, 2: invalid-date, missing-sender, invalid-amount` |
| `tab-separated` | Tab-separated content | Staged, `1: invalid-date, missing-sender, invalid-amount` |
| `separator-inside-unquoted-field` | `Kowalski; Jan` unquoted | Refused, 400 invalid-structure (five columns) |

### Quotes

| Case | File | Expected |
| --- | --- | --- |
| `quoted-separator` | `"Kowalski; Jan"` | Staged, `1: ok`, the sender keeps the `;` |
| `doubled-quotes` | `"Fundacja ""Dobro"""` | Staged, `1: ok`, the sender is `Fundacja "Dobro"` |
| `newline-in-quoted-field` | A sender with a newline inside quotes | Staged, `1: ok, 2: ok` (records numbered, newline kept) |
| `quote-inside-unquoted-field` | `Jan "Junior"` | Staged, `1: ok`, the quotes are kept as text |
| `unclosed-quote` | An opening quote that never closes | Refused, 400 parse-failed (no line swallowed into another) |

### Dates

| Case | File | Expected |
| --- | --- | --- |
| `impossible-iso-date` | `2026-02-30` | Staged, `1: invalid-date` |
| `impossible-polish-date` | `30.02.2026` | Staged, `1: invalid-date` |
| `us-date` | `01/15/2026` | Staged, `1: invalid-date` |
| `two-digit-year` | `15.01.26` | Staged, `1: invalid-date` |
| `future-date` | `2099-12-31` | Staged, `1: ok`. **Open question:** no rule refuses future dates. |
| `very-old-date` | `1900-01-01` | Staged, `1: ok`. **Open question:** no lower bound. |
| `date-with-spaces` | ` 2026-01-15 ` | Staged, `1: ok`, date `2026-01-15` (trimmed) |

### Amounts

| Case | File | Expected |
| --- | --- | --- |
| `space-thousands` | `1 000,00` | Staged, `1: invalid-amount` |
| `dot-thousands-and-comma-decimals` | `1.000,00` | Staged, `1: invalid-amount` |
| `dot-thousands-without-decimals` | `1.000` | Staged, `1: ok`, amount `1.000` (one zloty, by the confirmed dot-or-comma decimal rule). **Open question, reported:** a Polish reader may mean one thousand. |
| `currency-symbol` | `100 zł` | Staged, `1: invalid-amount` |
| `currency-code` | `PLN 100` | Staged, `1: invalid-amount` |
| `scientific-notation` | `1e3` | Staged, `1: invalid-amount` |
| `zero` | `0,00` | Staged, `1: invalid-amount` |
| `five-decimals` | `10,12345` | Staged, `1: invalid-amount` |
| `seventeen-digits` | `12345678901234567,00` | Staged, `1: invalid-amount` |
| `empty-amount` | empty | Staged, `1: invalid-amount` |
| `negative-amount` | `-50,00` | Staged, `1: ok`. The reconciliation then blocks it as `unsupported-amount` (refund rules are open). |
| `plus-sign` | `+10,00` | Staged, `1: ok` |

### Fields

| Case | File | Expected |
| --- | --- | --- |
| `empty-sender` | empty sender | Staged, `1: missing-sender` |
| `sender-at-the-cell-limit` | 4096 characters | Staged, `1: ok` |
| `sender-over-the-cell-limit` | 4097 characters | Refused, 413 resource-limit |
| `nul-byte` | a NUL byte in a name | Refused, 400 invalid-structure |
| `control-character` | a BEL character in a name | Staged, `1: ok`, kept as written |
| `emoji` | an emoji in a name | Staged, `1: ok`, kept |
| `polish-letters` | `Zażółć Gęślą` | Staged, `1: ok`, kept |
| `right-to-left-override` | U+202E in a name | Staged, `1: ok`, kept. Display spoofing is a UI concern; see the security tests. |

### Formula injection

| Case | File | Expected |
| --- | --- | --- |
| `formula-equals` | `=1+1` | Staged, `1: ok`, stored as plain text |
| `formula-plus` | `+48 600 100 200` | Staged, `1: ok`, plain text |
| `formula-minus` | `-2+3` | Staged, `1: ok`, plain text |
| `formula-at` | `@SUM(A1)` | Staged, `1: ok`, plain text |

There are no exports yet, so escaping formulas on export is checked when exports exist.

### Whole files

| Case | File | Expected |
| --- | --- | --- |
| `bom-only` | only a UTF-8 BOM | Refused, 400 invalid-structure |
| `truncated-mid-row` | the last line cut after the sender | Staged, `1: ok, 2: invalid-amount` |
| `binary-junk` | random bytes named `.csv` | Refused, 400 parse-failed |
| `xlsx-named-csv` | an XLSX workbook named `.csv` | Refused, 400 parse-failed |
| `csv-named-xlsx` | a CSV named `.xlsx` | Refused, 400 parse-failed |
| `just-under-the-size-limit` | about 5 MiB of valid rows | Staged, every row valid |
| `over-the-row-limit` | 50 001 rows | Refused, 413 resource-limit |

### XLSX

| Case | File | Expected |
| --- | --- | --- |
| `xlsx-truncated-archive` | a workbook cut in half | Refused, 400 parse-failed |
| `xlsx-two-sheets` | two sheets | Refused, 400 invalid-structure |
| `xlsx-formula` | a formula cell | Refused, 400 unsupported-format |
| `xlsx-merged-cells` | merged cells | Refused, 400 unsupported-format |
| `xlsx-fifth-column` | a cell in column E | Refused, 400 invalid-structure |
| `xlsx-date-as-text` | the date as text | Staged, `1: ok` |
| `xlsx-date-as-serial` | a date serial with a date format | Staged, `1: ok`, the date read correctly |
| `xlsx-1904-date-system` | a 1904-system date serial | Staged, `1: ok`, the same date |
| `xlsx-serial-without-date-format` | a number without a date format | Staged, `1: invalid-date` (not guessed) |
| `xlsx-hidden-row` | a hidden row | Staged, `1: ok, 2: ok` (hidden rows are not dropped) |

## Covered elsewhere, or not automated here

| Case | Where / why |
| --- | --- |
| An empty file | `tests/api/test_bank_upload.py::test_empty_file_is_rejected` (400 empty-file) |
| One byte over the 5 MiB limit | `tests/api/test_bank_upload.py::test_file_over_the_size_limit_is_rejected` (413) |
| An unsupported extension | `tests/api/test_bank_upload.py::test_unsupported_extension_is_rejected` (415) |
| XLSX zip bomb, XML entities (XXE, billion laughs) | The security tests (upload security) |
| An XLSX with very many rows | The row limit is the parser's, shared by both formats; checked on CSV (`over-the-row-limit`) to keep the suite fast. |
| Comma separator | `tests/api/test_bank_upload.py::test_comma_separated_csv_is_accepted` |

## Open questions for dev and the product owner

- **Future and very old dates are accepted.** Should a transfer dated 2099, or
  1900, stay valid?
- **`1.000` is read as one zloty.** The rule "a dot or a comma is the decimal
  separator" is confirmed, but a Polish reader may mean one thousand. Should a
  dot followed by exactly three digits be refused as ambiguous?
- **Control characters and right-to-left marks in names are kept.** Should they
  be refused or stripped?
