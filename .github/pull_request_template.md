## Summary

<!-- What this adds or changes, in a sentence or two. -->

**Mirrors dev branch:** <!-- e.g. `trello/35-bank-parser`, or "n/a" -->

## Changes

-

## How to run

<!-- ALMA_APP_REPO points at a checkout of the matching dev branch; orchestrated runs are serial. -->

```sh
uv run pytest -n0
```

## Checklist

- [ ] Merge order respected: the matching dev branch is merged to dev `main` first, and stacked test branches merge in order
- [ ] Static checks pass (CI): `ruff check`, `ruff format --check`, `mypy`, `pytest --collect-only`
- [ ] App-backed run against the matching dev branch (`-n0`)
- [ ] Follows AGENTS.md: numbered steps, assertion helpers with `described_as`, Polish UI strings as constants
- [ ] Synthetic data only, no real personal data
