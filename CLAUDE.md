# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
source scripts/env.sh                 # build //:gazelle_polyglot, export GAZELLE_BIN
bash scripts/ci_local.sh              # manifest check, unit tests, golden, fixture, mutation, ordering
python3 -m unittest discover -s tests # unit tests only (no Bazel; drift tests skip without GAZELLE_BIN)
bash scripts/lint.sh                  # ruff, shellcheck, actionlint
python3 tools/validate_manifest.py    # corpus manifest is complete and pinned
```

Run tools as scripts (`python3 tools/x.py`), not with `python3 -I`: they import `common` from their own directory.

## Architecture Overview

Plain Python scripts (standard library only) drive a polyglot Gazelle binary (`//:gazelle_polyglot`). `tools/gate.py` turns
corpus, benchmark and mutation results into pass/fail using `thresholds.json`. `tests/support.py` provides fake gazelle and
bazel executables so the runners can be tested without Bazel. See README.md and docs/specs/ for the criteria (C1-C7).

## Conventions & Patterns

- Tests live in `tests/`, use `unittest`, and must not need network or Bazel unless skipped on a missing `GAZELLE_BIN`.
- Every GitHub Action is pinned to a full commit SHA and every job has `timeout-minutes` (enforced by `tests/test_ci_workflow.py`).
- A gate criterion listed in `--require` must produce rows; a missing measurement fails, it never passes silently.
- Changing `thresholds.json`, `bench_results/baseline.json` or `corpus/manifest.json` changes what CI accepts: explain why in the PR.
- Decisions that are hard to reverse go in `docs/decisions/`.
