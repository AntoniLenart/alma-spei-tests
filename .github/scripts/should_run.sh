#!/usr/bin/env bash
# Usage: should_run.sh <event-name> <dev-sha>
#
# Prints "run=true" or "run=false" for $GITHUB_OUTPUT. A scheduled check runs the
# regression only for a dev commit without a published report yet (the report on
# the gh-pages branch records the dev commit it tested in `last-dev-sha`); every
# other trigger - manual, dispatch, pull request - always runs.
set -euo pipefail

event="$1"
sha="$2"

if [ "$event" != "schedule" ]; then
  echo "run=true"
  exit 0
fi

last="$(gh api "repos/${GITHUB_REPOSITORY}/contents/last-dev-sha?ref=gh-pages" --jq .content 2>/dev/null \
  | base64 -d 2>/dev/null | tr -d '[:space:]' || true)"
echo "Dev main: ${sha}; last tested: ${last:-none}" >&2

if [ "$sha" = "$last" ]; then
  echo "run=false"
else
  echo "run=true"
fi
