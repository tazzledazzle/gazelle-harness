#!/usr/bin/env bash
# Prints the environment block for a failure report.
echo "date: $(date -u +%FT%TZ)"
echo "os: $(uname -sm)"
echo "bazel: $(bazel --version 2>&1 | head -n 1)"
echo "python: $(python3 --version 2>&1)"
echo "git: $(git --version)"
echo "java: $(java -version 2>&1 | head -n 1)"
echo "gazelle: ${GAZELLE_BIN:-unset}"
echo "commit: $(git rev-parse --short HEAD 2>/dev/null)"
git status --short | head -n 20