#!/usr/bin/env bash
# Usage: tools/gazelle_check.sh [workspace-dir]
# Exit 0 = clean, 1 = BUILD files are stale (drift), 2 = Gazelle itself failed.
set -uo pipefail                                              # no -e: every exit status below is handled explicitly
WS="${1:-.}"                                                  # directory to check; default current
: "${GAZELLE_BIN:?set GAZELLE_BIN (source scripts/env.sh)}"   # refuse to run without a binary
STDERR_FILE="$(mktemp)"                                       # warnings go here, kept out of the diff
trap 'rm -f "$STDERR_FILE"' EXIT                              # the file used to be left behind on every run
# diff mode prints what WOULD change and writes nothing; -repo_root pins the root explicitly
DIFF="$(cd "$WS" && "$GAZELLE_BIN" -mode=diff -repo_root="$PWD" 2>"$STDERR_FILE")"
STATUS=$?
if [[ -n "$DIFF" ]]; then                                     # any diff output means drift
  echo "$DIFF"
  echo "gazelle_check: BUILD files are stale; run Gazelle in $WS without -mode=diff" >&2
  exit 1
fi
if [[ $STATUS -ne 0 ]]; then                                  # failure with no diff: tool error, not drift
  cat "$STDERR_FILE" >&2
  echo "gazelle_check: Gazelle failed with exit code $STATUS" >&2
  exit 2
fi
echo "gazelle_check: clean"