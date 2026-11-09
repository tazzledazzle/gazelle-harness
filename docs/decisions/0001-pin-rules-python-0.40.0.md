# 0001: Pin rules_python to 0.40.0 (root module and polyglot fixture)

Status: accepted, 2026-11-09

## Context

`.bazelversion` pins Bazel 8.4.2. `rules_python` 2.4.3 failed to load there: its `MODULE.bazel` uses the Starlark
builtin `flag_alias`, which Bazel 8.4.2 does not define (`name 'flag_alias' is not defined`). The root module hit this
first; the polyglot fixture (`fixtures/polyglot/input/MODULE.bazel`) still pinned 2.4.3 and would hit it in the fixture
build.

## Decision

Pin `rules_python` to 0.40.0 in both `MODULE.bazel` and the fixture module, alongside `rules_python_gazelle_plugin`
0.40.0. A unit test (`tests/test_manifest.py`) fails if the two versions diverge.

## Consequences

- Python rules are older than current. Revisit when `.bazelversion` moves to a release that defines `flag_alias`,
  and bump `rules_python`, `rules_python_gazelle_plugin` and the fixture together.
- The Gazelle Python extension under test is the one shipped with 0.40.0; results for newer extension releases are not
  covered until that bump.
