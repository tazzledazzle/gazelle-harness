#!/usr/bin/env bash
# Creates a throwaway git repo and a manifest that points at it, to test tools/corpus_run.py.
set -e
cd "$(git rev-parse --show-toplevel)"
D=.corpus/_selftest_src
rm -rf "$D" && mkdir -p "$D/a"
echo 'package a' > "$D/a/a.go"
echo '# stripped by the fetch tool' > "$D/a/BUILD.bazel"      # proves stripping works
git -C "$D" init -q
git -C "$D" add -A
git -C "$D" -c user.name=t -c user.email=t@t commit -q -m init
COMMIT="$(git -C "$D" rev-parse HEAD)"
cat > .corpus/selftest_manifest.json <<EOF
{"fork_owner": "x", "repos": [{"id": "selftest", "language": "go", "upstream": "$PWD/$D", "fork_repo": "x", "commit": "$COMMIT", "strip_dirs": ["*"], "gazelle_args": [], "gazelle_directives": ["# gazelle:prefix example.com/selftest"], "targets": [], "bazel_version": "", "notes": "runner self-test"}]}
EOF
echo "wrote .corpus/selftest_manifest.json"