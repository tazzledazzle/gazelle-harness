#!/usr/bin/env bash
# Fast checks and the polyglot fixture; the same commands CI runs on every pull request.
set -e
cd "$(git rev-parse --show-toplevel)"
python3 tools/validate_manifest.py                       # cheap and offline: fail before any Bazel work if the corpus manifest is unfinished
source scripts/env.sh                                    # builds the binary and exports GAZELLE_BIN
python3 -m unittest discover -s tests -v                 # all unit tests (drift check needs GAZELLE_BIN)
bazel test //golden:golden_test                          # golden cases through Bazel
python3 golden/run_golden.py --gazelle "$GAZELLE_BIN" --cases-dir fixtures   # polyglot fixture expectations
python3 tools/mutate.py --golden-case fixtures/polyglot --gazelle "$GAZELLE_BIN"       # C3
python3 tools/check_order.py --golden-case fixtures/polyglot --gazelle "$GAZELLE_BIN"  # H6
if [ -n "$CI_BUILD_FIXTURE" ]; then                      # slow: needs network for Bazel dependencies
  python3 tools/fixture_build.py --gazelle "$GAZELLE_BIN"
fi