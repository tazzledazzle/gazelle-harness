# gazelle-harness

A test and benchmark harness for Gazelle BUILD-file generation across Python, Java, Kotlin and JS/TS. It turns the
seven acceptance criteria in [docs/specs/build-generation-specs.md](docs/specs/build-generation-specs.md) into
pass/fail checks: golden tests, mutation and ordering checks, a corpus of real repositories, and benchmarks.

The tooling is plain Python (standard library only) driving a polyglot Gazelle binary built by Bazel. Linux and macOS only.

## Status

| Language | In `gazelle_polyglot` |
|---|---|
| Go, proto | yes (ship with Gazelle) |
| Python, Java, Kotlin | yes |
| JS/TS | **not yet**: the `ts` corpus entries use `-lang=js` and fail until an extension is added |

## Quick start

```bash
source scripts/env.sh          # builds //:gazelle_polyglot and exports GAZELLE_BIN
bash scripts/ci_local.sh       # what CI runs on every pull request
bash scripts/lint.sh           # ruff, shellcheck, actionlint (pip install -r requirements-dev.txt first)
```

Needs Bazelisk on `PATH` as `bazel` (it reads `.bazelversion`), Python 3.12 and git.

## What runs when

| Stage | Trigger | Runs |
|---|---|---|
| `lint` | every pull request | `scripts/lint.sh` |
| `checks` | every pull request | unit tests, golden cases, polyglot fixture, mutation (C3), ordering, fixture build |
| `corpus` | nightly, manual, or PR label `corpus` | each repo in `corpus/manifest.json`: regenerate, build, test, compare dependency edges (C1) |
| `bench` | nightly or manual | synthetic repos at 1,000 and 10,000 packages (C2) |
| `gate` | nightly or manual | `tools/gate.py` applies `thresholds.json` to everything above and fails on a missing result |

## Layout

| Path | Purpose |
|---|---|
| `tools/` | corpus fetch/run, dependency diff, mutation and ordering checks, benchmarks, the gate, manifest validator |
| `golden/` | golden-case runner and cases (`input/` plus `expected/`); also run as a Bazel `py_test` |
| `fixtures/polyglot/` | one workspace with every language, used for the build check |
| `corpus/manifest.json` | pinned upstream repositories (forked under `fork_owner`) and per-repo settings |
| `thresholds.json` | limits for C1, C2, C3; changes need review (see `CODEOWNERS`) |
| `bench_results/baseline.json` | recorded benchmark baselines |
| `docs/decisions/` | architecture decision records |

## Common tasks

**Add a golden case.** Create `golden/cases/<lang>/<name>/input/` (use `BUILD.in` for a starting BUILD file) and optional
`arguments.txt`, then `python3 golden/run_golden.py --gazelle "$GAZELLE_BIN" --cases-dir golden/cases --filter <name> --update`.
Review the generated `expected/` in the diff; `--update` refuses output that is not idempotent.

**Add a corpus repo.** Fork it under `fork_owner`, add an entry to `corpus/manifest.json`, pin it with
`python3 tools/corpus_fetch.py --id <id> --use-upstream --pin`, add the id to the `corpus` matrix in
`.github/workflows/ci.yml`, and run `python3 tools/validate_manifest.py`. Tests fail if the matrix and manifest disagree.

**Record benchmark baselines.** Run the `ci` workflow manually with `record_baseline` set, download the
`baseline-merged` artifact and commit it as `bench_results/baseline.json`. Record on the same runner type the nightly uses.

**Reproduce a corpus failure.** `python3 tools/corpus_run.py --id <id> --gazelle "$GAZELLE_BIN" --depdiff`;
logs land in `.corpus/<id>/logs/`. `scripts/report_env.sh` prints the environment block for a bug report.
