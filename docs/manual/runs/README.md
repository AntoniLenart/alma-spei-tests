# Run records

One file per manual run, named `<YYYY-MM-DD>-<tester>-<scope>.md` and copied from
[`../templates/execution-record.md`](../templates/execution-record.md). A record
always states the date and the app version (dev `main` commit). Every failure in
it links its bug or UX card.

| Run | Tester | App version | Scope | Result |
| --- | --- | --- | --- | --- |
| [2026-11-28 full](2026-11-28-antoni-full.md), [sessions](2026-11-28-antoni-exploratory.md) | Antoni | dev `main` @ a722a1a | All acceptance scenarios, five exploratory sessions, accessibility, Polish texts, Chrome / Firefox / Edge | 39 of 39 scenario runs passed; 3 bug cards and 4 UX cards; screen reader checks not run |
