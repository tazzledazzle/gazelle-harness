# BUILD generation specs: Python, Kotlin, Java, JS/TS

Oct 30, 2026 · @Terence Schumacher

Bringing Gazelle-based BUILD generation to all seven "strong" criteria is a small-to-medium job for JS/TS, Python and Java, and a large one for Kotlin, whose extension is still experimental. Rough effort for one engineer who already knows Gazelle: JS/TS 3–4 weeks, Python 5–7, Java 6–8, Kotlin 10–14 (on top of the shared JVM core counted in Java's estimate). These are estimates made before any baseline measurement, so treat them as sizing, not commitments.

## Overview

Each language spec has four parts: the gap per criterion, the proposed code changes, the tests and verification, and the milestones. Criteria are numbered C1–C7 and defined once in the shared foundation section.

- **Evidence base.** Current-state claims come from public package docs, READMEs, release notes and registry pages found in search on 2026-10-30. Several of those pages are older snapshots, so version numbers may be stale.
- **Code paths.** File and package names are taken from public repo listings and package docs. I have not read the source. Each spec therefore opens with a baseline audit that confirms or corrects what it assumes.
- **Proposed names.** Directive names and flags marked *proposed* are placeholders to be settled with each project's maintainers.
- **Out of scope.** Windows hosts beyond what each spec names. Kotlin Multiplatform and Kotlin/Android generation are a later phase, described at the end of the Kotlin spec.

## Shared foundation

The seven criteria become pass/fail only when each has a number and a test, so every language spec reuses the definitions and harness below. Thresholds are *proposed* starting points; set them after the baseline run.

### The seven criteria as testable requirements

| ID | Criterion                           | Testable requirement                                                                                                                  | How it is verified                                                                                                            |
|----|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| C1 | Accurate import-to-label resolution | On the corpus, zero missing deps and at most 2% unneeded deps, including third-party and generated code                               | Strict-deps builds (Java/Kotlin), import validation (Python), `ts_project` type-check build (JS/TS), plus an unused-deps scan |
| C2 | Fast, incremental at monorepo scale | No-op run under 10 s and single-file change under 2 s on a 10,000-package synthetic repo                                              | Benchmark harness, 5 runs, p95                                                                                                |
| C3 | Merge-safe                          | A second run produces zero diff; hand edits, keep markers, mapped macros and extra attributes survive regeneration                    | Idempotence and mutation tests                                                                                                |
| C4 | CI drift detection                  | CI fails on any difference between committed and generated BUILD files, naming the files and the fix command                          | Negative test: stale BUILD file must turn CI red                                                                              |
| C5 | Granularity control                 | Per-file, per-package and per-module (or project) modes selectable by directive per subtree; switching modes keeps the repo buildable | Mode-matrix test                                                                                                              |
| C6 | Test and macro awareness            | Tests, custom macros, annotation processors, compiler plugins and bundlers produce the right kinds and attributes                     | One fixture per macro or plugin                                                                                               |
| C7 | One command for the polyglot repo   | `bazel run //:gazelle` generates all four languages plus proto from one binary, with cross-language conflicts resolved                | Polyglot fixture repo                                                                                                         |

### Shared test harness

1. **Golden tests per extension.** Input tree plus expected BUILD output, following Gazelle's `testdata` convention. Run them with `gazelle_generation_test`, which `rules_python` already considers for its plugin.
2. **Corpus tests.** The corpus is a fixed set of real open-source repositories used as realistic test inputs: three per language, each pinned to one commit. Delete their BUILD files, regenerate, then run `bazel build //...` and `bazel test //...`. Pass means green with zero hand fixes.
3. **Round-trip equivalence.** Where a repo already has hand-written BUILD files, compare generated dependency edges to the hand-written ones with `bazel query` and report missing and extra edges.
4. **Idempotence and order independence.** Run twice and expect no diff; shuffle directory traversal order and expect identical output.
5. **Mutation tests for C3.** Programmatically add a keep marker, a custom attribute, a renamed macro and a deleted target, rerun, and assert what survives.
6. **Performance benchmark.** A generator script builds synthetic repos of 1k, 10k and 50k packages. Record wall time, peak memory and parser invocations for cold, no-op and single-file-change runs.
7. **Drift test (C4).** CI runs Gazelle in its diff mode and fails on any output. `gazelle_test` is not cacheable, so use a CI script or pre-commit hook rather than relying on it alone.

### Shared code changes

- **One polyglot binary.** A single `gazelle_binary` combining the Go and proto defaults, Aspect's JS extension, the Python extension, the Java extension and the Kotlin extension. Aspect's pre-compiled binaries cover JS, Python and its own extension language only, so Java and Kotlin force a source-built binary.
- **Ordering and collisions.** Define which extension owns a directory when Java and Kotlin sources mix, and which one wins when two extensions claim the same rule name. Cover this in the C7 fixture.
- **Shared checks.** A `tools/gazelle_check` script wrapping the drift test, the idempotence test and the benchmark so every language reuses them.

## Harness and polyglot fixture: implementation plan

The harness is a two-week build that must land before any language work merges, because every language spec's acceptance criteria run on it. It lives in one repository (name *proposed*: `gazelle-harness`) that consumes each extension as a Bazel module, so it can test forks during development and released versions afterwards.

### Repository layout

```
gazelle-harness/
  MODULE.bazel            # extension modules, pinned in versions.bzl
  BUILD.bazel             # //:gazelle_polyglot binary, //:gazelle_check
  corpus/                 # manifest.yaml, corpus_repo rule, per-repo expectations
  golden/                 # gazelle_golden_test macro, shared testdata helpers
  tools/                  # depdiff, mutate, synth, bench, gate
  fixtures/polyglot/      # the C7 monorepo and its golden outputs
  thresholds.yaml         # C1 to C6 numbers, one reason line each
  ci/                     # pipeline definitions
```

### Components

#### H1: corpus manager

- **Manifest:** `corpus/manifest.yaml` lists, per repo, the fork URL, the upstream URL, the pinned commit (a commit in the fork), language, BUILD files to strip, and the target patterns that must build and pass.
- **Rule:** `corpus_repo` is a repository rule that fetches the pinned commit, copies existing BUILD and module files to `original_builds/` for comparison, then deletes them from the build tree. Fetch from your own fork of each repository, never from upstream, so upstream deletions or history rewrites cannot break CI.
- **Selection rules:** permissive licence; already builds with Bazel (so a working oracle exists); deterministic dependencies; size cap; three repos per language chosen with the open question on private repos answered first.
- **Acceptance:** fetching is reproducible from a clean cache; stripped trees contain no Bazel files.

#### H1 selection: proposed corpus

I chose by fit to the harness, not by star count, because the highest-starred Bazel projects are mostly C++ or already unusual in ways that would hide generator bugs. Each pick had to be permissively licensed, already build with Bazel (so a working oracle exists), show activity in 2026, and stress at least one of C1 to C7. This is a first selection from public pages; I have not read licence files, measured sizes or built any of them.

| Language   | Repository                              | Why it earns a slot                                                                                                         | Licence              | To confirm                                                                                                 |
|------------|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|----------------------|------------------------------------------------------------------------------------------------------------|
| Java       | google/dagger                           | Annotation processors and generated classes (C1, C6); Bazel with a lockfile for Maven dependencies                          | Apache-2.0 (seen)    | Size; which targets build offline                                                                          |
| Java       | grpc/grpc-java                          | Protobuf-generated code; Bazel and Gradle side by side; built with and without Bzlmod in its own CI                         | Apache-2.0 (seen)    | Bazel 9 status                                                                                             |
| Java       | GerritCodeReview/gerrit                 | Real application on Bazel 9.1 with Bzlmod, plugins, and a mixed Java, JS and Python tree; the scale probe for C2            | Apache-2.0 (confirm) | Too large for the size cap: use a server subset for correctness runs and the full tree only for benchmarks |
| Kotlin     | grpc/grpc-kotlin                        | Mostly Kotlin, with Java and protobuf; Bazel CI; published on the registry                                                  | Apache-2.0 (confirm) | Supports Bzlmod only, and JDK 22 at most, so it cannot join the WORKSPACE variant                          |
| Kotlin     | Tinder/bazel-diff                       | A real Kotlin application and CLI with Kotlin tests, built with Bazel                                                       | MIT (confirm)        | Bzlmod-only mode; test depth                                                                               |
| Kotlin     | bazelbuild/rules\_kotlin (examples)     | Compiler plugins, Dagger and Android examples for C6; **provisional**, since it is a set of examples and not an application | Apache-2.0 (confirm) | Replace if a real third Kotlin application on Bazel turns up                                               |
| Python     | ray-project/ray (Python subtree)        | Large real Python code with Bazel test targets and protobuf-generated Python                                                | Apache-2.0 (confirm) | Mostly C++ build files: strip and regenerate only Python ones                                              |
| Python     | google/pigweed (Python modules)         | Python on Bazel with pinned pip dependencies and a managed interpreter                                                      | Apache-2.0 (seen)    | Same: Python files only; embedded toolchains out of scope                                                  |
| Python     | aspect-build/bazel-examples (Python)    | Small, current, clean setup; the control case                                                                               | Apache-2.0 (seen)    | None known                                                                                                 |
| TypeScript | angular/components                      | Large TypeScript codebase on current `rules_js` and `rules_ts` with Bzlmod and pnpm                                         | MIT (confirm)        | Size; Angular-specific rules wrapping `ts_project` (good for C3 and C6)                                    |
| TypeScript | angular/angular-cli                     | Another Angular-org project moved to `rules_js` in 2025                                                                     | MIT (confirm)        | Whether it still builds on current Bazel                                                                   |
| TypeScript | aspect-build/bazel-examples (JS and TS) | Non-Angular frameworks and test runners: React, Next.js, NestJS, Vue, Jest, for the runner and bundler work                 | Apache-2.0 (seen)    | None known                                                                                                 |

Notes on the selection:

- **Reuse for the polyglot fixture:** `aspect-build/bazel-examples` is a polyglot monorepo, so it is the natural seed for the C7 fixture in H9.
- **WORKSPACE variant:** only repositories that still support WORKSPACE can join it; `grpc-kotlin` cannot.
- **Commits:** fork each repository into your organization before the first fetch, keep its licence files intact, never sync a fork automatically, and pin each manifest entry to a commit in the fork that builds, recording the Bazel version used.
- **Private repositories:** still open; the corpus manifest supports them, but the choice is yours. The organization that will own the forks is not yet named.

#### H2: golden test runner

- **Macro:** `gazelle_golden_test(name, binary, testdata)` wraps Gazelle's generation-test rule. Each case is a directory with inputs, `BUILD.in` and `BUILD.out`.
- **Update mode:** a companion `bazel run` target rewrites `BUILD.out` from current output, reviewed by diff.
- **Acceptance:** each extension's existing tests run through the macro unchanged.

#### H3: corpus runner

- **Flow:** copy a stripped corpus repo to a scratch workspace, run `//:gazelle_polyglot`, then run `bazel build //...` and `bazel test //...` inside it. Use the nested-Bazel integration-test rules that `rules_python` already depends on.
- **Output:** one `results.json` per repo with build status, test status and timings.
- **Isolation:** pin the nested Bazel version through a version file; share a remote cache between runs.
- **Acceptance:** a known-good repo passes end to end; a deliberately broken extension fails.

#### H4: dependency diff and gate

- **`tools/depdiff`:** query generated and original targets and report, per target, missing and extra deps, as JSON.
- **`tools/gate`:** read `thresholds.yaml` plus the JSON from H3, H4 and H7 and exit non-zero on any breach, printing the criterion ID and the failing number.
- **Acceptance:** unit tests for the diff on small hand-made graphs; the gate fails on a planted regression.

#### H5: mutation tester (C3)

- **Mutations:** `mutations.yaml` lists operations applied to generated BUILD files with buildozer: add an attribute, add a keep marker, rename a rule kind to a wrapper macro and map it back, delete a target, reorder attributes.
- **Assertion per mutation:** survives regeneration, or is restored, as stated in the file.
- **Acceptance:** the suite runs on every extension; a deliberately destructive fixture fails it.

#### H6: idempotence and order checks

- **Idempotence:** run twice and diff.
- **Order:** run once for the whole repo, then once per directory in a shuffled order with a fixed seed, and require identical output.
- **Acceptance:** both pass on all golden cases and corpus repos; a planted order-dependent bug is caught.

#### H7: synthetic repos and benchmark (C2)

- **`tools/synth`:** deterministic generator, seeded, producing 1k, 10k and 50k packages per language with a layered dependency graph, configurable fan-out and optional cycles.
- **`tools/bench`:** cold, no-op and one-file-change runs, five each, recording wall time, peak memory and parser invocations. Parser counts need a small shared change: each extension prints a stats line when `GAZELLE_STATS=1` is set.
- **Stability:** run on a dedicated runner class; report p95; fail on more than a 15% regression against the stored baseline (*proposed*).
- **Acceptance:** repeat runs on one machine agree within 5%.

#### H8: drift check (C4)

- **`gazelle_check`:** runs Gazelle in its diff mode over a copy of the workspace, prints the diff and fix command, exits non-zero on any difference. A script rather than a cached test, because `gazelle_test` cannot be cached.
- **Negative test:** a fixture with a stale BUILD file must make the check fail.
- **Acceptance:** green on clean trees, red on the stale fixture.

#### H9: polyglot fixture and binary (C7)

- **Binary:** `//:gazelle_polyglot` composes the Go and proto defaults, Aspect's JS extension, the Python extension, the Java extension and the Kotlin extension, with extension order fixed and documented. Versions live in `versions.bzl`; development overrides point at forks.
- **Fixture contents:** one small monorepo with a Java library and service, a Kotlin service, a mixed Java/Kotlin directory, a Python service, a TypeScript web app, and one shared proto package generating code for all four languages. It carries a Maven lockfile, a pip lockfile and a pnpm lockfile.
- **Cross-language edges:** Kotlin depends on the Java library; every language consumes the proto output; the web app imports generated TypeScript.
- **Conflict cases:** two extensions claim one rule name; a mixed directory; the same import string meaning different packages in different languages.
- **Expectations:** golden BUILD outputs for the whole tree, plus `bazel build //...` and `bazel test //...` passing.
- **Acceptance:** one command regenerates everything with no diff against the goldens; every conflict case has a documented outcome.

### CI pipeline

| Stage        | Trigger                              | Runs                                  |
|--------------|--------------------------------------|---------------------------------------|
| 1. Fast      | every pull request                   | H2 golden tests, H6, H8 negative test |
| 2. Polyglot  | pull requests touching any extension | H9 fixture, H5 mutation suite         |
| 3. Corpus    | nightly and on a label               | H3 and H4 for each language           |
| 4. Benchmark | nightly                              | H7 against baseline                   |

Matrix: Bazel 8 and 9 with Bzlmod, plus Bazel 8 with legacy WORKSPACE (the polyglot fixture gets a WORKSPACE variant), on Linux and macOS; add Windows only if the open question says so.

### Build order

1. **Days 1–2:** skeleton, `versions.bzl`, `//:gazelle_polyglot` with the extensions that exist today, H2 golden macro.
2. **Days 3–4:** H1 corpus rule, forks of the twelve repositories, and manifests; H4 `depdiff`.
3. **Days 5–6:** H3 corpus runner; `thresholds.yaml` with placeholders; H4 gate.
4. **Days 7–8:** H5 mutation tester; H6 idempotence and order checks; H8 drift check.
5. **Days 9–10:** H7 synthetic generator and benchmark; H9 fixture skeleton with Java, Python and JS/TS only; CI stages 1 and 2.
6. **Then:** extend the fixture with Kotlin when its extension compiles, and turn on CI stages 3 and 4 once corpora are chosen.

### Risks and mitigations

| Risk                                  | Mitigation                                                                                |
|---------------------------------------|-------------------------------------------------------------------------------------------|
| Nested Bazel runs are slow or flaky   | Pin Bazel version, share a remote cache, run corpora nightly rather than per pull request |
| Corpus repos disappear or change      | Pinned commits in forks of every corpus repository                                        |
| Benchmark noise hides regressions     | Dedicated runner class, five runs, p95, 15% gate with a stored baseline                   |
| Fixture drifts from real repositories | Seed fixture modules from corpus subsets and review them each quarter                     |
| Extensions lack a stats flag          | Small shared patch counted inside each language's performance work package                |
| Extension order changes output        | Fix and document order; add a test that fails on reordering                               |

### Definition of done

All nine components pass their acceptance checks, `thresholds.yaml` holds measured numbers with reasons, and a language extension can be added to the harness by editing only `versions.bzl`, the corpus manifest and one fixture directory.

## JS/TS spec

JS/TS is closest to strong already: the work is hardening resolution edge cases, proving scale, and adding test-runner and bundler awareness, roughly 3–4 weeks.

### Current state

Aspect's extension generates `ts_project`, `npm_package` and `npm_link_all_packages` targets and resolves imports against `pnpm-lock.yaml`. It offers directives for generation mode, library and test file globs, tsconfig handling, and glob-aware `js_resolve` and `js_ignore_imports`. Aspect markets incremental runs and CI drift detection for its Gazelle. BenchSci's separate `rules_nodejs_gazelle` also generates `jest_test` and `web_asset` rules and supports Webpack and Next.js.

### Gap per criterion

| ID | Gap today                                                                                                                                                                                                              | Work                                                                                                                                                                | Done when                                      |
|----|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------|
| C1 | Edge cases unverified: tsconfig `paths` aliases, `package.json` `exports` and subpath imports, workspace-protocol packages, type-only `@types/*` deps, generated TS (protobuf, GraphQL codegen), CSS and asset imports | Build an edge-case fixture, fix each failure in the resolver, add `js_resolve` presets for common codegen outputs                                                   | Corpus builds with zero hand-added deps        |
| C2 | Incrementality claimed, not measured                                                                                                                                                                                   | Benchmark; add a parse cache keyed on file hash; confirm directory-scoped runs skip unchanged subtrees                                                              | C2 thresholds met at 10k packages              |
| C3 | Behaviour with wrapper macros around `ts_project` unknown                                                                                                                                                              | Verify `map_kind` and keep markers across all generated kinds; fix gaps                                                                                             | Mutation suite passes                          |
| C4 | Drift detection is in a commercial product description; OSS path unconfirmed                                                                                                                                           | Use the shared drift check; document it for the OSS binary                                                                                                          | Stale BUILD turns CI red                       |
| C5 | Available granularities unconfirmed                                                                                                                                                                                    | Confirm directory-level mode; add a per-tsconfig-boundary mode (*proposed*) because `ts_project` maps to one tsconfig; add per-file only if benchmarks show it pays | Mode matrix builds                             |
| C6 | Test targets follow `js_test_files` globs; runner-specific rules (Jest, Vitest, Mocha) and bundler targets (Webpack, Vite, esbuild, Next.js) unconfirmed in the Aspect extension                                       | Add a pluggable test-kind mapping, e.g. `js_test_runner jest` (*proposed*), emitting `jest_test` via `rules_jest`; evaluate porting BenchSci's bundler detection    | Fixture per runner and bundler builds and runs |
| C7 | Aspect's binary does not include Java or Kotlin                                                                                                                                                                        | Include Aspect's JS extension in the shared source-built binary                                                                                                     | C7 fixture passes                              |

### Code changes

- **`aspect-cli/gazelle/js`** (Go): the `Configurer`, `GenerateRules`, `Imports`, `Resolve` and `Fix` entry points. Add resolver stages for tsconfig `paths` and `package.json` `exports`; add a codegen-output index; add the runner mapping and boundary-granularity directive.
- **Parse cache**: a content-hash cache of extracted imports, stored outside the repo (e.g. a per-user cache dir) and disabled with a flag.
- **Diagnostics**: a `--strict` mode that fails on any unresolved import and lists the file, the import string and the directive that would fix it.
- **Fixtures**: a new `testdata/` directory per edge case under the extension's existing test layout.

### Tests and verification

- Golden tests for every edge case in the C1 row, each with a `BUILD.out`.
- Corpus: three open-source pnpm monorepos, one each of React, Node service and library-only. Regenerate and run `bazel build //...` and `bazel test //...`.
- Type-check as oracle: a missing dep makes `ts_project` fail under `tsc`; an unneeded dep is found by a script that diffs declared deps against actual imports.
- Benchmarks at 1k, 10k and 50k packages; record cold, no-op and one-file-change times.
- Mutation tests for C3 and a negative test for C4.

### Milestones

1. Baseline audit and benchmark (3–4 days).
2. Resolver edge cases and fixtures (1 week).
3. Test runner and bundler mapping (1–1.5 weeks).
4. Granularity mode, drift check, polyglot integration (1 week).

### Implementation spec

Five work packages deliver the four milestones, and every change ships behind a directive whose default leaves current output unchanged, so upstream review and existing users carry no risk. Directive names are *proposed*.

#### WP0: baseline audit (milestone 1)

- **Change:** add `audit/js/run.sh` that regenerates BUILD files for each corpus repo and writes `report.json` with unresolved imports, extra deps, wall time and peak memory.
- **Also records:** Bazel 8 and 9 compatibility with Bzlmod, which directives and granularities exist today, and whether drift detection ships in the open-source binary.
- **Acceptance:** report committed; C2 thresholds re-set from measured numbers with the reasoning written next to them.

#### WP1: resolver pipeline (milestone 2)

- **Change:** refactor import resolution into an ordered chain behind one interface, `Resolver.Resolve(import, pkgConfig) (Label, Kind, Diagnostic)`: relative path, then tsconfig `paths`, then workspace package, then npm package through the lockfile, then codegen index, then `js_resolve` overrides.
- **tsconfig paths:** load each tsconfig once with its `extends` chain, cache the parsed mapping per directory, and match longest prefix first.
- **npm `exports`:** map subpath imports to the owning package; do not evaluate conditions beyond `types`, `import` and `default`.
- **`@types`:** when an import resolves to a package with a sibling `@types/` entry in the lockfile, add both labels.
- **Codegen index:** directive `js_codegen_output <glob> <label>` maps generated files to the target that produces them.
- **Strict mode:** `-js_strict` fails the run listing file, import string and the directive that would fix it.
- **Acceptance:** one golden case per edge case in the C1 row; corpus builds with zero hand-added deps.

#### WP2: test runners and bundlers (milestone 3)

- **Change:** register `jest_test` (and Vitest and Mocha equivalents) in the kinds table; directive `js_test_runner jest|vitest|mocha|none`.
- **Detection:** read `devDependencies` and config files (`jest.config.*`, `vitest.config.*`) to pick a runner when none is set; never guess when both are present, emit a warning instead.
- **Bundlers:** port BenchSci's Webpack and Next.js detection behind `js_bundler`, off by default, after checking its licence and ownership with the authors.
- **Acceptance:** fixture per runner builds and passes; bundler fixtures build.

#### WP3: scale (milestones 1 and 4)

- **Change:** content-hash parse cache keyed on file bytes and parser version, stored under the user cache directory, disabled with `-js_cache=false`.
- **Incremental runs:** document and test directory-scoped runs (`bazel run //:gazelle -- <dir>`) and ensure unchanged subtrees are skipped.
- **Concurrency:** bound worker count and expose it as a flag so CI hosts with few cores stay stable.
- **Acceptance:** C2 thresholds at 10k packages; cache hit rate reported by the benchmark.

#### WP4: granularity, drift and polyglot (milestone 4)

- **Change:** `js_granularity directory|tsconfig|file`; `tsconfig` emits one `ts_project` per tsconfig boundary.
- **Switching test:** regenerate under each mode and require a green `bazel build //...` each time.
- **Drift:** wire the shared `gazelle_check` target; add a negative test.
- **Polyglot:** add the extension to the shared source-built binary and run the C7 fixture.

#### Risk mitigations in this spec

| Risk                             | Mitigation here                                                                        |
|----------------------------------|----------------------------------------------------------------------------------------|
| Parser or resolver cost at scale | WP3 cache and benchmark gate before WP1 merges                                         |
| Upstream rejection               | Design issue per directive before coding; defaults unchanged                           |
| Bazel 9 or Bzlmod gaps           | WP0 check; CI matrix on Bazel 8 and 9 with Bzlmod, plus a WORKSPACE variant on Bazel 8 |
| Guessed thresholds               | WP0 resets them from measured numbers                                                  |
| Windows                          | Out of scope unless the open questions say otherwise; add a Windows job only then      |

#### Definition of done

All seven criteria pass on the corpus, the benchmark report is committed, and each upstream change has an open or merged pull request.

## Python spec

Python needs the manifest workflow automated and made incremental, a measured parser, and test-macro support, roughly 5–7 weeks. A first decision gates everything: adopt the `rules_python` plugin or Aspect's Python generator.

### Current state

The `rules_python` plugin generates `py_library`, `py_binary` and `py_test`. It needs a `gazelle_python.yaml` manifest, built by the `modules_mapping` rule, to map import names to pip packages; the manifest is checked in because computing it is slow in large monorepos, and a `.test` target checks it is current. Generation mode is `package` or `project`, import validation defaults to on, and Gazelle leaves unrelated edits alone. Older docs describe parsing through a Python subprocess, but recent release notes mention tree-sitter, so the current parser needs confirming. The Gazelle plugin may be broken on Windows as of 1.8.0. Aspect's pre-compiled Gazelle also lists Python generators.

### Decision to make first

Pick one base before any code. `rules_python`'s plugin is the community default and ships with the rules. Aspect's generator may be faster or easier to combine with its JS extension. Run both through the baseline audit on the same corpus and choose on C1, C2 and C7 results. The rest of this spec assumes the `rules_python` plugin.

### Gap per criterion

| ID | Gap today                                                                                                                                                                                     | Work                                                                                                                                                                        | Done when                                                |
|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| C1 | Manifest is a manual step; likely weak spots: namespace packages, stub-only and `types-*` packages, extras, multiple pip hubs and Python versions, generated code (protobuf and gRPC outputs) | Layered resolver: first-party index, then manifest keyed per hub and version, then generated-code index, then `gazelle:resolve py` overrides; keep validation on by default | Corpus builds; import validation reports zero unresolved |
| C2 | `modules_mapping` is slow at scale; parser cost unmeasured                                                                                                                                    | Make `modules_mapping` one action per wheel plus a merge step so a dependency bump recomputes one wheel; benchmark and, if needed, batch parser calls                       | C2 thresholds met; single-wheel bump under 30 s          |
| C3 | Non-destructive by design; custom wrapper macros around `py_*` untested                                                                                                                       | Verify `map_kind` and keep markers for all three kinds; fix gaps                                                                                                            | Mutation suite passes                                    |
| C4 | Manifest has a `.test` target; BUILD drift has none                                                                                                                                           | Shared drift check plus the manifest test in one CI job                                                                                                                     | Stale BUILD or stale manifest turns CI red               |
| C5 | `package` and `project` modes exist; no per-file mode confirmed                                                                                                                               | Confirm; add `file` mode (*proposed*) so one changed module does not invalidate a whole package                                                                             | Mode matrix builds                                       |
| C6 | Tests are files ending in `_test.py`; likely gaps: `test_*.py` and pytest conventions, `conftest.py` sharing, fixture data, pytest wrapper macros                                             | Add configurable test file patterns (*proposed*), `conftest.py` as shared dep, `map_kind` for pytest macros, default `data` globs for test directories                      | Pytest fixture repo generates and passes                 |
| C7 | Windows support uncertain; one-binary composition untested                                                                                                                                    | Resolve the Windows issue or document the limit; include in shared binary                                                                                                   | C7 fixture passes                                        |

### Code changes

- **`rules_python/gazelle`** (Go): `configure.go` and `pythonconfig/` for new directives; `resolve.go` for the layered resolver; `generate.go` and `target.go` for file mode and test patterns; `parser.go` and `parse.py` for parser profiling and batching; `std_modules.go` to keep the standard-library list current per Python version.
- **`gazelle/modules_mapping`** (Starlark and generator script): per-wheel actions with a merge step, and a cache-friendly output format.
- **`gazelle/manifest`**: a `--check` mode used by the shared drift job.
- **`testdata/`**: one golden case per gap above, following the existing layout.
- **Automation**: a bot or pre-commit step that reruns the manifest target when a requirements lockfile changes.

### Tests and verification

- Golden tests for each C1 and C6 gap, plus multi-hub and multi-version cases.
- Corpus: three open-source Python repos, one app, one library, one with protobuf. Regenerate, run `bazel build //...` and `bazel test //...`, require import validation clean.
- Manifest correctness: for a fixed lockfile, compare the new per-wheel manifest byte-for-byte with the old whole-set output.
- Benchmarks at 1k, 10k and 50k packages, cold and incremental, including a dependency-bump scenario.
- Mutation tests for C3, drift negative test for C4, and a Windows CI job if Windows stays in scope.

### Milestones

1. Baseline audit; decision between the two Python generators (1 week).
2. `modules_mapping` per-wheel rework and manifest check (1–1.5 weeks).
3. Layered resolver and generated-code index (1.5–2 weeks).
4. Test patterns, `conftest.py`, macro mapping (1 week).
5. Granularity mode, drift check, Windows decision, polyglot integration (1–1.5 weeks).

### Implementation spec

Six work packages deliver the five milestones. The first one produces a decision, so the others are written against the `rules_python` plugin and should be redone if the audit picks Aspect's generator instead. Directive names are *proposed* unless a package already documents them.

#### WP0: baseline audit and base decision (milestone 1)

- **Change:** run both Python generators on the same three-repo corpus and score them on C1, C2 and C7 into one table.
- **Decision rule:** take the `rules_python` plugin unless Aspect's generator has fewer missing deps and is not slower than half the plugin's speed on the C2 benchmark. Write the result and reasoning into the repo.
- **Also records:** whether the parser is a Python subprocess or tree-sitter (docs conflict), the Bazel 8 and 9 and Bzlmod status, the supported Python versions, and whether the Windows issue reproduces.
- **Acceptance:** scorecard committed; decision recorded; C2 thresholds reset from measurements.

#### WP1: per-wheel module mapping (milestone 2)

- **Change:** split `modules_mapping` into a per-wheel rule that runs the generator once per wheel and writes one JSON file, plus a merge action that produces the single mapping the manifest rule reads.
- **Compatibility:** keep the existing macro signature as a wrapper so current users change nothing.
- **Edge cases handled in the generator:** `top_level.txt`, namespace packages, stub-only distributions (`-stubs` and `types-*`), and distribution-name sanitising.
- **Manifest check:** add a `--check` mode to the manifest tool and a CI target that fails when the manifest is stale.
- **Automation:** a pre-commit step reruns the manifest target when any requirements lockfile changes.
- **Acceptance:** for a fixed lockfile, new output equals old output byte for byte; bumping one wheel reruns one generator action and finishes in under 30 s.

#### WP2: layered resolver (milestone 3)

- **Change in `resolve.go`:** a chain behind one interface: first-party index, manifest keyed by pip hub and Python version, generated-code index, then `gazelle:resolve py` overrides, then a diagnostic.
- **Manifest schema:** add a version field and a per-entry hub name; keep reading the old schema.
- **Generated code:** register import names produced by proto-generated Python targets through Gazelle's cross-language import index; fall back to a `python_resolve_generated` directive.
- **Strict mode:** keep import validation on by default and add `-python_strict` to fail with file, import and suggested directive.
- **Standard library:** generate the module table in `std_modules.go` from the interpreter's own list for each supported version, with a CI check that the table is current.
- **Acceptance:** multi-hub and multi-version golden cases pass; corpus builds with zero unresolved imports.

#### WP3: parser performance (milestones 1 and 3)

- **Change:** profile first. If the parser is a subprocess, replace per-file calls with one persistent worker speaking a line protocol, or move to in-process tree-sitter. If it is already tree-sitter, add a content-hash parse cache keyed on file bytes and parser version.
- **Acceptance:** C2 thresholds at 10k packages with parser invocations reported by the benchmark.

#### WP4: tests and macros (milestone 4)

- **Change:** configurable test file patterns for `*_test.py`, `test_*.py` and pytest layouts; `conftest.py` generated as a test-only library and added to tests in the same and child directories.
- **Macros:** audit `map_kind` for `py_library`, `py_binary` and `py_test`, fix any kind that skips the mapping, and add a `python_test_data <glob>` default for fixture files.
- **Acceptance:** a pytest fixture repo with a wrapper macro generates, builds and passes.

#### WP5: granularity, drift, Windows, polyglot (milestone 5)

- **File mode:** one `py_library` per module. Detect import cycles between files and either merge the cycle into one target with a warning or fail with the cycle listed, chosen by directive. Cycles are common in Python, so this is the main risk of the mode.
- **Drift:** shared `gazelle_check` plus the manifest check in one job.
- **Windows:** if in scope, reproduce the reported Gazelle issue as a failing CI job first, then fix path handling; if not, mark the generator targets incompatible with Windows and document it.
- **Polyglot:** add to the shared binary; run the C7 fixture.

#### Risk mitigations in this spec

| Risk                        | Mitigation here                                                                                                                        |
|-----------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| Parser cost dominates       | WP3 profiles before any resolver work merges                                                                                           |
| Wrong base generator chosen | WP0 scorecard and written decision rule                                                                                                |
| Upstream rejection          | Design issue first; schema and directive changes are additive; old manifests keep working                                              |
| Bazel 9 or Bzlmod gaps      | WP0 check; CI on Bazel 8 and 9, plus a WORKSPACE variant on Bazel 8 (pip hub names differ there, so the manifest keys must cover both) |
| Guessed thresholds          | WP0 resets them                                                                                                                        |
| Windows                     | WP5 decision with a reproducing test                                                                                                   |

#### Definition of done

All seven criteria pass on the corpus, manifest output is byte-identical to the old path, and the base-generator decision is written down.

## Java spec

Java needs processor-aware resolution, automatic cycle handling, a faster parser path and a shared core that Kotlin can reuse, roughly 6–8 weeks.

### Current state

The `rules_jvm` extension generates `java_library`, `java_binary`, `java_test` and `java_test_suite`. It reads external dependency data from `maven_install.json`, is configured through directives such as `java_extension`, `java_maven_install_file` and `java_test_file_suffixes`, and generates tests either as one suite per directory or one test per file. Parsing runs in a side-process Java program. The README documents a known pain point: dependency cycles between packages, worked around by coarser module granularity at the cost of slower builds. The last package-docs snapshot I found was v0.29.0 from May 2025. I did not confirm Bzlmod or Bazel 9 compatibility.

### Gap per criterion

| ID | Gap today                                                                                                                                                                                                                                                                                    | Work                                                                                                                                                                                                        | Done when                                                         |
|----|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| C1 | Likely weak spots: classes produced by annotation processors (Dagger, AutoValue, Immutables, MapStruct, Lombok), `exports` inference for API types, packages split across targets, Bzlmod lockfile formats and multiple Maven repos, static and wildcard imports, protobuf-generated classes | Processor-aware resolution with a declared generated-class map (*proposed* directive), `exports` inference for types in public signatures, ambiguity diagnostics for split packages, Bzlmod lockfile reader | Strict-deps build passes with zero hand-added deps on corpus      |
| C2 | Each parse crosses into a separate JVM program                                                                                                                                                                                                                                               | Long-lived parser process with batched requests; content-hash parse cache; benchmark                                                                                                                        | C2 thresholds met at 10k packages                                 |
| C3 | Custom `java_library` wrapper macros and attributes such as `plugins`, `javacopts`, `runtime_deps`, `visibility` unverified                                                                                                                                                                  | `map_kind` and keep-marker audit across all generated kinds; never overwrite non-generated attributes                                                                                                       | Mutation suite passes                                             |
| C4 | None built in; the lockfile has its own staleness check                                                                                                                                                                                                                                      | Shared drift check plus a lockfile-pin check in the same CI job                                                                                                                                             | Stale BUILD or stale lockfile turns CI red                        |
| C5 | Package and module granularity; cycles need manual coarsening                                                                                                                                                                                                                                | Automatic strongly-connected-component merging: when packages form a cycle, emit one merged target and a warning naming the members; add per-file granularity (*proposed*)                                  | Cyclic fixture generates a buildable repo with no directive edits |
| C6 | Suite and per-file test modes exist; custom test macros, JUnit 5 runner settings, test resources and annotation-processor plugin attributes unconfirmed                                                                                                                                      | Map test kinds through `map_kind`; derive `plugins` from the processor declaration; attach resources and `jvm_flags` defaults                                                                               | Fixture per macro builds and runs                                 |
| C7 | Kotlin and Java may share directories                                                                                                                                                                                                                                                        | Define ownership for mixed directories; shared Maven and package index                                                                                                                                      | C7 fixture passes                                                 |

### Code changes

- **`rules_jvm/java/gazelle`** (Go): resolution and generation entry points; add the processor map, `exports` inference, the SCC-merging pass in resolve, and the lockfile reader.
- **`javaconfig/config.go`**: new directives for generated classes, granularity, and cycle behaviour, with the same inheritance rules as existing ones.
- **Parser side process** (`javaparser/generators:Main`): add a persistent mode that reads requests from standard input and returns results in batches, keeping the one-shot mode for compatibility.
- **Shared JVM core** (new package, e.g. `jvmcore`): move the Maven index, package-to-target index, granularity and cycle logic out of the Java extension so the Kotlin extension imports the same code. Do this behind existing tests with no behaviour change first.
- **`testdata/`**: one golden case per gap above.

### Tests and verification

- Golden tests per C1 and C6 gap, including a cyclic-package case and a split-package case.
- Corpus: three open-source Java repos using Maven dependencies, one with Dagger or AutoValue, one with protobuf. Regenerate, then `bazel build //...` and `bazel test //...` with strict Java deps on.
- Unneeded-dep scan with the buildtools `unused_deps` tool; the target is at most 2% extra.
- Refactor safety: before and after moving code into `jvmcore`, generated output across the whole corpus must be byte-identical.
- Benchmarks at 1k, 10k and 50k packages for cold, no-op and one-file change, comparing one-shot and persistent parser modes.
- Mutation tests for C3 and drift negative test for C4.

### Milestones

1. Baseline audit, Bzlmod and Bazel 9 check, benchmark (1 week).
2. Extract the shared JVM core with zero output change (1–1.5 weeks).
3. Persistent parser and cache (1 week).
4. Processor-aware resolution and `exports` inference (1.5–2 weeks).
5. SCC merging and granularity modes (1 week).
6. Test macro mapping, drift check, polyglot integration (1 week).

### Implementation spec

Six work packages deliver the six milestones. The shared JVM core in WP1 is the dependency that Kotlin waits on, so it has a strict no-behaviour-change gate and its interfaces are written for two consumers from the start. Directive names are *proposed*.

#### WP0: baseline audit (milestone 1)

- **Change:** regenerate the Java corpus, record missing and extra deps, timings, and which processors the corpus uses.
- **Also records:** Bazel 8 and 9 and Bzlmod compatibility, the lockfile format used under Bzlmod, and the current default granularity.
- **Acceptance:** report committed; C2 thresholds reset; a design issue opened with the `rules_jvm` maintainers describing WP1 before any code lands.

#### WP1: shared JVM core (milestone 2)

- **Step 1, characterise:** snapshot the extension's current output on the whole corpus as golden files. Nothing moves until these exist.
- **Step 2, extract:** create a `jvmcore` Go package inside the `rules_jvm` Gazelle module with four parts behind interfaces: a Maven index with a pluggable `LockfileReader`, a package-to-target index, a granularity strategy, and a cycle resolver. Move code without editing it, one part per commit.
- **Step 3, document:** write the exported interfaces with examples; Kotlin consumes them unchanged.
- **Gate:** generated output across the corpus is byte-identical before and after every commit.
- **Acceptance:** golden files unchanged; unit tests for each interface; Kotlin skeleton compiles against the package.

#### WP2: persistent parser and cache (milestone 3)

- **Protocol:** newline-delimited JSON over standard input and output. A request carries an id and a path; a response carries the package, imports, declared types, public-signature types and any parse errors. Batches of up to 64 files per round trip.
- **Lifecycle:** the Go side starts the worker when configuration finishes and stops it when generation ends. If the worker crashes or times out, retry once, then fall back to the one-shot path for the remaining files and log it.
- **Startup cost:** enable class-data sharing for the worker JVM and reuse one process for the whole run.
- **Cache:** content-hash cache keyed on file bytes and parser version under the user cache directory; `-java_cache=false` disables it.
- **Acceptance:** C2 thresholds at 10k packages; crash-recovery and protocol tests pass; output identical to one-shot mode.

#### WP3: processors and exports (milestone 4)

- **Generated classes:** directive `java_generated_classes <annotation> <name-pattern>` with an embedded data file of presets for Dagger, AutoValue, Immutables and MapStruct, so adding a processor needs data, not code. For Dagger the patterns cover component, factory and members-injector names.
- **Plugins:** directive `java_plugin <annotation> <label>` derives the `plugins` attribute; Lombok needs only this, since it adds no new classes.
- **Exports:** parse types in public and protected signatures and, when `java_infer_exports` is on (default off), add those deps to `exports`.
- **Split packages:** when one package maps to several targets, emit a diagnostic listing candidates and require a `gazelle:resolve java` override rather than guessing.
- **Lockfile reader:** implement the `LockfileReader` interface for the Bzlmod-era format and the older `maven_install.json`; confirm during WP0 whether they are identical.
- **Acceptance:** Dagger, AutoValue and protobuf fixtures build under strict Java deps; unneeded-dep scan at most 2%.

#### WP4: cycles and granularity (milestone 5)

- **Constraint:** a Bazel target lives in one directory's BUILD file, so merging packages that sit in different directories means placing one target at their closest common ancestor with sources collected from below.
- **Design:** a pre-pass, run after the parse cache is warm, builds the package import graph, finds strongly connected components, and for each one that spans directories sets module granularity at the ancestor directory in memory. Generation then proceeds as normal. Validate this design with a prototype on the cyclic fixture before building the rest.
- **Warning:** every merge logs the member packages so users can break the cycle if they want finer targets.
- **Per-file mode:** one library per file; files that import each other in a cycle merge by the same algorithm.
- **Acceptance:** cyclic fixture builds with no hand-added directives; mode matrix builds.

#### WP5: tests, drift and polyglot (milestone 6)

- **Test macros:** audit `map_kind` for all four kinds; add `java_test_resources` to attach resource globs; set runner and `jvm_flags` defaults for JUnit 5.
- **Drift:** shared `gazelle_check` plus a lockfile-pin check in one job.
- **Mixed directories:** the core exposes one policy, `MixedDir(dir)`. When Kotlin is enabled, the Kotlin extension owns the directory's library and takes the `.java` files into its sources, and the Java extension emits nothing there. Without Kotlin, nothing changes.
- **Polyglot:** add to the shared binary; run the C7 fixture.

#### Risk mitigations in this spec

| Risk                       | Mitigation here                                                                                                                       |
|----------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| Parser cost dominates      | WP2 before any resolver work; benchmark gates merging                                                                                 |
| Upstream rejection         | Design issue before code; WP1 is behaviour-neutral and reviewable alone; new behaviour sits behind directives with unchanged defaults |
| Bazel 9 or \Bzlmod gaps    | WP0 check; `LockfileReader` interface isolates the format; WORKSPACE variant on Bazel 8                                               |
| Cycle merging design wrong | WP4 prototype before full build                                                                                                       |
| Kotlin blocked on the core | WP1 interfaces reviewed with the Kotlin plan; skeleton compile check in acceptance                                                    |
| Guessed thresholds         | WP0 resets them                                                                                                                       |

#### Definition of done

All seven criteria pass on the corpus, WP1's byte-identical gate holds through every later change, and the exported core interfaces are documented for Kotlin.

## Kotlin spec

Kotlin is the largest gap: no extension is ready for use today, so this is a build-or-extend decision followed by roughly 10–14 weeks of work on top of the shared JVM core created in the Java spec.

### Current state

Aspect's Kotlin extension, in the `aspect-cli` repo, targets `kt_jvm_library` and `kt_jvm_binary`. Its package docs call it experimental and not ready for use, with resolution of Maven dependencies through `rules_jvm` still upcoming; Gazelle's own list says only that it is still under development. A separate early work-in-progress extension uses `rules_kotlin` and `grpc-kotlin`, relies on `rules_jvm_external` data, was modelled on the Java extension, and has no Bzlmod support. A proposal to place a Kotlin extension next to `rules_kotlin` or `rules_jvm` was open, with Aspect considering donating its code; I found no resolution. `rules_kotlin` itself ships frequent 2.3.x releases.

### Decision to make first

| Option                                                       | Pros                                                                                                           | Cons                                                                                 |
|--------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| A. Contribute to Aspect's extension                          | Existing code, a maintainer team, likely upstream path                                                         | Experimental state, unknown test depth, design not yet matching the shared JVM core  |
| B. New Kotlin extension on the shared JVM core (recommended) | Reuses Maven, package and cycle logic from Java, so C1, C2, C5 and C7 behave identically across both languages | New parser and Kotlin-specific resolver to write; must coordinate upstream placement |
| C. Adopt the standalone project                              | Smallest start                                                                                                 | Early stage, no Bzlmod, less maintained                                              |

Run the baseline audit on A and C against the Kotlin corpus first. If either builds three corpus repos with under 10% hand fixes, prefer extending it; otherwise take option B and borrow ideas from both.

### Gap per criterion

| ID | Gap today                                                                                                                                                                                                                                                                             | Work                                                                                                                                                                                             | Done when                                                          |
|----|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| C1 | Kotlin-specific resolution is unbuilt: same-package files with no import, top-level functions and properties compiled to `FileNameKt` classes, extension functions, typealiases, `import ... as` aliases, star imports, Java interop in mixed targets, implicit standard-library deps | Declaration index per file (package, top-level symbols, typealiases); resolver using the shared JVM core's Maven and package indexes; implicit-stdlib handling; mixed Java/Kotlin target support | Strict-deps style build passes on corpus with zero hand-added deps |
| C2 | No performance data                                                                                                                                                                                                                                                                   | Parser choice benchmarked: in-process tree-sitter Kotlin versus the Kotlin compiler's syntax tree in a side process; hash-keyed parse cache; worker-count control                                | C2 thresholds met at 10k packages                                  |
| C3 | Untested for `kt_*` macros                                                                                                                                                                                                                                                            | `map_kind`, keep markers and attribute preservation for all generated kinds                                                                                                                      | Mutation suite passes                                              |
| C4 | None                                                                                                                                                                                                                                                                                  | Shared drift check plus lockfile check                                                                                                                                                           | Stale BUILD turns CI red                                           |
| C5 | Library per directory only, if that                                                                                                                                                                                                                                                   | Per-package, per-module and per-file modes shared with Java, including automatic cycle merging                                                                                                   | Mode matrix builds; cyclic fixture builds                          |
| C6 | Compiler plugins and symbol processors unmodelled: kotlinx.serialization, Compose compiler, KSP, kapt (Hilt, Room, Moshi codegen); test frameworks (JUnit 5, Kotest)                                                                                                                  | Plugin declarations map to `rules_kotlin` plugin attributes; generated-class map shared with Java; test naming and kind rules                                                                    | Fixture per plugin and framework builds and runs                   |
| C7 | Java and Kotlin may share directories and the Maven index                                                                                                                                                                                                                             | Ownership rules for mixed directories; one binary                                                                                                                                                | C7 fixture passes                                                  |

### Code changes

- **New Kotlin extension package** (Go), either upstream in `rules_kotlin` or `rules_jvm`, or in Aspect's `gazelle/kotlin`. Language registration, `Configurer`, `GenerateRules`, `Imports`, `Resolve` and `Fix`, with kinds `kt_jvm_library`, `kt_jvm_binary` and `kt_jvm_test`.
- **Kotlin parser**: a function that returns package, imports with aliases, top-level declarations and typealiases per file. Keep the choice behind an interface so both parser candidates can be benchmarked.
- **Imports to `jvmcore`**: Maven index, package index, granularity and cycle logic from the shared core built in the Java spec; no copies.
- **Directives** (*proposed*): `kt_enabled`, `kt_maven_repo`, `kt_plugin`, `kt_test_framework`, `kt_generation_mode`, matching the Java directive style so one mental model covers both.
- **Bzlmod**: lockfile and repo-name handling from day one, not a later retrofit.
- **`testdata/`**: one golden case per resolution and plugin gap above.

### Tests and verification

- Golden tests for every C1 and C6 case, including a mixed Java/Kotlin target and a cyclic-package case.
- Corpus: three open-source Kotlin JVM repos with Maven dependencies, one using KSP or kapt, one with kotlinx.serialization or coroutines, one server app with tests. Regenerate, then `bazel build //...` and `bazel test //...`.
- Dependency precision: unused-dependency scan and a missing-dependency scan from build failures. I did not confirm that `rules_kotlin` offers a strict-deps check equivalent to Java's, so verify early and, if absent, add a Kotlin-import-versus-deps checker as part of this work.
- Equivalence with Java: run the shared JVM core's regression corpus after the Kotlin extension is added; Java output must stay byte-identical.
- Benchmarks at 1k, 10k and 50k packages for both parser candidates.
- Mutation tests for C3, drift negative test for C4, and the C7 polyglot fixture.

### Milestones

1. Baseline audit of options A and C; decision (1–1.5 weeks).
2. Parser interface and benchmark of both candidates (1–1.5 weeks).
3. Declaration index and resolver on the shared core (3 weeks).
4. Compiler plugin and symbol processor support (2–3 weeks).
5. Test framework support and mixed Java/Kotlin targets (2 weeks).
6. Granularity modes, Bzlmod hardening, drift check, polyglot integration (1.5–2 weeks).

### Implementation spec

Six work packages deliver the six milestones, written for option B (a new extension on the shared JVM core). If the WP0 audit shows option A or C is close enough, WP1 to WP3 become contributions to that project instead, and the work-package contents carry over as the contribution plan. Directive names are *proposed*, and names of `rules_kotlin` constructs must be confirmed in WP0.

#### WP0: audit, decision and upstream proposal (milestone 1, time-boxed to 1.5 weeks)

- **Audit:** run Aspect's extension and the standalone project on the Kotlin corpus. Score each on hand fixes needed, Bzlmod support, and test depth.
- **Decision rule:** if either builds all three corpus repos with under 10% hand-fixed targets, extend it. Otherwise proceed with option B and record why.
- **Also confirm:** the current `rules_kotlin` rule and macro names and load paths, its compiler-plugin and KSP-plugin declarations, whether a strict-deps check exists for Kotlin, and Bazel 9 compatibility.
- **Upstream proposal:** a short written proposal to the `rules_kotlin`, `rules_jvm` and Aspect maintainers naming where the extension should live, who owns it, and what CI it needs. Start development without waiting for the answer, in a repository you control, laid out the way the upstream home would expect.
- **Acceptance:** scorecard, decision and proposal committed.

#### WP1: parser interface and benchmark (milestone 2)

- **Interface:** `Parse(path) FileInfo`, where `FileInfo` holds the package, imports (with alias and star flags), top-level declarations (functions, properties, classes, objects, typealiases, with receiver for extension functions), annotations, and whether the file defines `main`.
- **Candidates:** an in-process tree-sitter parser, and a side process using the Kotlin compiler's syntax tree speaking the same batched protocol as the Java worker.
- **Evaluate on:** correctness against the compiler on at least 1,000 corpus files (package, imports and top-levels must match), speed, memory, and build impact. Tree-sitter bindings need cgo, which complicates cross-compiled Gazelle binaries; weigh that explicitly.
- **Cache:** reuse the content-hash cache design from the Java worker.
- **Acceptance:** written comparison; one parser chosen; the other kept behind the interface only if it earns its place.

#### WP2: declaration index and resolver (milestone 3)

- **Index:** map from package to targets, and from fully qualified top-level symbol to target. Kotlin imports can name functions and properties, so a class-only index is not enough.
- **Resolution order for an import:** first-party symbol, then first-party package (star imports), then the shared Maven index, then implicit Kotlin default imports and standard library, then Java sources in the same target.
- **Aliases and typealiases:** resolve `import x as y` by the original name; a typealias creates a dependency on the target holding its declaration.
- **Same-package use without imports:** scan identifiers in each file against the same-package symbol index and add deps for matches. This over-approximates, so track the extra-dep rate in C1 and tune.
- **Oracle tool:** if WP0 finds no strict-deps check, build `kt-depcheck`, a small tool on the same parser that compares a target's imports with its declared deps. Use it in corpus tests and offer it to users.
- **Acceptance:** golden cases for each rule above; corpus builds with zero hand-added deps; extra-dep rate at or under 2%.

#### WP3: plugins and processors (milestone 4)

- **Plugin mapping:** directive `kt_plugin <annotation-or-import-prefix> <label>` sets the compiler-plugin or KSP attribute; presets for kotlinx.serialization (detect `@Serializable`) and common KSP and kapt users.
- **Generated classes:** reuse the Java extension's generated-class presets for Dagger and Hilt, and add Room and Moshi code generation.
- **Compose:** mapping only, no Android generation.
- **Acceptance:** one fixture per plugin and processor builds and runs.

#### WP4: tests and mixed targets (milestone 5)

- **Frameworks:** detect JUnit 5 and Kotest from imports; directive `kt_test_framework` overrides; generate `kt_jvm_test` with the right runner attributes; test names `*Test.kt` and `*Spec.kt`.
- **Internal visibility:** when tests live beside their module and use `internal` members, generate the association attribute `rules_kotlin` provides for that purpose (confirm its name in WP0).
- **Mixed Java and Kotlin:** use the Java spec's `MixedDir` policy; the Kotlin extension owns the library and includes `.java` files in its sources.
- **Acceptance:** JUnit 5 and Kotest fixtures pass; a mixed-directory fixture builds; Java extension output unchanged when Kotlin is disabled.

#### WP5: granularity, Bzlmod, drift, polyglot (milestone 6)

- **Granularity:** per-file, per-package and per-module modes via the shared core, including the cycle pre-pass from the Java spec.
- **Bzlmod:** repo-name handling and the `LockfileReader` from the start; CI on Bazel 8 and 9.
- **Drift and polyglot:** shared `gazelle_check`; add to the shared binary; run the C7 fixture on all four languages.

#### Risk mitigations in this spec

| Risk                                      | Mitigation here                                                                                                                   |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| Build-or-extend decision slips            | WP0 time-box and written decision rule                                                                                            |
| Upstream placement unresolved             | Proposal in WP0; development in a repo laid out for later transfer; additive directives                                           |
| Parser cost or build complexity           | WP1 benchmark before resolver work; cgo impact weighed explicitly                                                                 |
| No Kotlin strict-deps check               | `kt-depcheck` oracle in WP2                                                                                                       |
| Same-package resolution over-approximates | Extra-dep metric tracked from the first corpus run                                                                                |
| Bazel 9 or Bzlmod gaps                    | WP0 check; Bzlmod built in from WP5 start; CI matrix, plus a WORKSPACE variant on Bazel 8 where the corpus repository supports it |
| Guessed thresholds                        | WP0 resets them                                                                                                                   |

#### Definition of done

All seven criteria pass on the Kotlin corpus, Java output is unchanged with Kotlin disabled, and the extension has an agreed home with an owner.

### Later phase: Kotlin Multiplatform and Android

Both are now in scope after the JVM work, so the JVM design must not foreclose them. I would not size this phase before its audit, because the main unknown is what Bazel rules exist to generate for.

#### What changes in the JVM work packages now

- **WP1 parser:** `FileInfo` also records `expect` and `actual` modifiers, the source-set name taken from the path, and references to the Android resource class.
- **WP2 index:** add a platform dimension (JVM, Android, other) to the symbol index, so an `expect` declaration can resolve to different `actual` targets per platform.
- **Rule-kind registry:** make the set of generated kinds a registry keyed by platform, instead of the three JVM kinds hard-coded.
- **Directives:** namespace them so platform-specific ones can be added without renames.

#### Phase work packages

- **WP6, Android audit and generation:** confirm the current `rules_android` kinds and Kotlin interop; read the manifest for the application package; map `res/` directories to resource targets; resolve `R` imports to the module that owns the resources; add presets for Hilt and Compose on Android; verify on an Android corpus.
- **WP7, Multiplatform audit:** establish whether Bazel rules exist for each Kotlin Multiplatform target (JVM, Android, JS, native). If a platform has no rules, generation for it has nothing to produce, and the phase stops for that platform. Where rules exist, map source sets such as `commonMain` and `jvmMain` to targets and resolve `expect` to `actual`.
- **Acceptance:** an Android app and a small multiplatform library from the corpus build under Bazel with zero hand-written dependencies.

#### Unknowns to settle in the audits

Current state of Bazel rules for Kotlin Multiplatform; whether Android generation needs resource-aware ordering inside the Gazelle run; how Bazel 9 and the legacy WORKSPACE variant affect `rules_android`; and whether the Android corpus fits the harness's nested-Bazel runs.

## Sequencing, risks and open questions

Total sizing is about 24–33 engineer-weeks across the four languages, not counting the later Kotlin Multiplatform and Android phase; with two engineers working in parallel that is roughly four months, with Kotlin on the critical path.

### Suggested order

1. Build the shared harness and polyglot fixture (2 weeks); every spec depends on it. In the same weeks, confirm licences, sizes and build status of the proposed corpus.
2. Run baseline audits for all four languages in parallel; settle the Python base and the Kotlin build-or-extend decision.
3. JS/TS and Python proceed in parallel; neither blocks Java.
4. Java extracts the shared JVM core early (its milestone 2), because Kotlin cannot start resolver work without it.
5. Kotlin starts parser benchmarking during the Java core work, then builds on the finished core.
6. Final integration: one binary, one CI job, the C7 fixture on all four languages.

### Risks

| Risk                                                                 | Effect                         | Mitigation                                                                                                 |
|----------------------------------------------------------------------|--------------------------------|------------------------------------------------------------------------------------------------------------|
| Kotlin option decision slips or upstream placement is unresolved     | Kotlin start delayed           | Time-box the audit to 1.5 weeks; build in a repo you control and upstream later                            |
| Parser cost dominates at 10k packages in Java or Kotlin              | C2 missed                      | Persistent parser and cache are already in plan; benchmark before building resolvers                       |
| Upstream maintainers reject directive or design changes              | Fork maintenance               | Open design issues with each project before coding; keep changes behind directives with unchanged defaults |
| Bazel 9 or Bzlmod incompatibilities in the Java or Kotlin extensions | Rework                         | Check in each baseline audit                                                                               |
| Thresholds are guesses                                               | False pass or fail             | Re-set after the first benchmark and record why                                                            |
| Windows hosts                                                        | Plugin gaps, as seen in Python | Decide scope up front; add a Windows CI job only if in scope                                               |

### Decisions so far

- **Support matrix:** Bazel 8 and 9 with Bzlmod, plus Bazel 8 with legacy WORKSPACE. Bazel 9 removed WORKSPACE, so the legacy variant cannot run there.
- **Kotlin Multiplatform and Android:** needed later. The JVM design carries the hooks now; the phase itself is unsized until its audits are done.
- **Ownership:** you and the fork contributors maintain forks and upstream relations.
- **Corpus:** a first selection of twelve repositories is proposed under H1 in the harness plan, pending licence, size and build checks. Each will be forked into your organization, and the harness fetches from the forks.

### Open questions

- Which Bazel version and module system (Bzlmod only, or legacy workspace too) must the extensions support? Decided: both Bzlmod and legacy WORKSPACE. Bazel 9 removed WORKSPACE entirely, so legacy support means Bazel 8 with WORKSPACE re-enabled by flag; Bazel 9 is Bzlmod only. Still open: how long to keep the WORKSPACE variant.
- Is Kotlin Multiplatform or Kotlin/Android generation needed later? Decided: yes, as a later phase; the end of the Kotlin spec lists what changes.
- Which three real repositories per language (the test corpus) are acceptable as test inputs, and can a private repo join the corpus? A first selection is proposed under H1 in the harness plan; private repositories are still open.
- Who maintains forks and upstream relations after the work lands? Decided: you and the fork contributors. Still open: whether each extension gets a named lead among them.

### Unverified assumptions

- Source-level details (function names, directive behaviour, parser implementations) come from package docs and release notes, not a code read.
- Java and Kotlin extension compatibility with Bazel 9 and Bzlmod.
- Whether `rules_kotlin` offers a strict-deps check for Kotlin.
- Which granularities and test patterns the current Python and JS/TS extensions already support.
- Whether Aspect's drift-detection feature is available in the open-source binaries; and the licences, sizes and current build status of the proposed corpus repositories.

### Sources

As of 2026-10-30. Read as search results, not fetched in full.

- [Gazelle (bazel-contrib)](https://github.com/bazel-contrib/bazel-gazelle) and [Gazelle v0.52.2 docs](https://pkg.go.dev/github.com/bazelbuild/bazel-gazelle@v0.52.2)
- [Gazelle Java extension](https://pkg.go.dev/github.com/bazel-contrib/rules_jvm/java/gazelle) and [its README change](https://github.com/bazel-contrib/rules_jvm/pull/372/files)
- [Aspect Kotlin extension](https://pkg.go.dev/aspect.build/cli/gazelle/kotlin), [standalone Kotlin extension](https://beta.pkg.go.dev/github.com/srmocher/gazelle-kotlin), [rules\_kotlin issue 1282](https://github.com/bazelbuild/rules_kotlin/issues/1282)
- [rules\_python Gazelle README](https://android.googlesource.com/platform/external/bazelbuild-rules_python/+/8048ff7/gazelle/README.md), [its directives](https://android.googlesource.com/platform/external/bazelbuild-rules_python/+/ccbb05e/gazelle/), [1.8.0 release notes](https://github.com/snape/HRVO/pull/25)
- [Aspect JS Gazelle extension](https://pkg.go.dev/aspect.build/cli/gazelle/js), [Aspect directives](https://docs.aspect.build/cli/help/directives), [Aspect build file generation](https://aspect.build/platform/build-file-generation), [Aspect Build GitHub](https://github.com/aspect-build)

Added for the support matrix and the corpus selection:

- [Bazel 9 LTS announcement](https://blog.bazel.build/2026/01/20/bazel-9.html)
- [Dagger repository listing](https://android.googlesource.com/platform/external/dagger2/+/refs/heads/upstream-master)
- [grpc-java CI workflow](https://github.com/grpc/grpc-java/blob/master/.github/workflows/testing.yml)
- [Gerrit Bazel rules (bazlets)](https://gerrit.googlesource.com/bazlets/+show/2ad832d89984267fe9a3336251a658f7e7b21e00/README.md)
- [grpc-kotlin](https://github.com/grpc/grpc-kotlin) and [bazel-diff](https://github.com/tinder/bazel-diff)
- [Ray build documentation](https://docs.ray.io/en/latest/ray-contribute/development.html) and [Pigweed WORKSPACE](https://android.googlesource.com/platform/external/pigweed/+/63c5be9f1/WORKSPACE)
- [angular/components Bazel dependency update](https://github.com/angular/components/pull/33642)
- [Aspect Bazel examples](https://beta.pkg.go.dev/github.com/aspect-build/bazel-examples) and [Aspect open-source list](https://docs.aspect.build/bazel/open-source)
