#!/usr/bin/env bash
# Source this file (do not execute it): builds the polyglot Gazelle binary and exports GAZELLE_BIN.
cd "$(git rev-parse --show-toplevel)" || return 1   # always work from the repo root
bazel build //:gazelle_polyglot || return 1          # cached when nothing changed
_rel="$(bazel cquery --output=files //:gazelle_polyglot 2>/dev/null | head -n 1)"  # built binary, relative path
export GAZELLE_BIN="$PWD/$_rel"                      # absolute so tools can run from any directory
echo "GAZELLE_BIN=$GAZELLE_BIN"