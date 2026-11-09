#!/usr/bin/env bash
# Static checks, the same ones CI runs in its lint job: pip install -r requirements-dev.txt && bash scripts/lint.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 -m ruff check .                                      # Python: style, unused names, import order, likely bugs
shellcheck -x scripts/*.sh tools/*.sh                        # shell scripts
actionlint .github/workflows/*.yml                           # workflow syntax, expressions and embedded shell
