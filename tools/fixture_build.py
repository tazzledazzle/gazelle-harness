#!/usr/bin/env python3
'''C7 build check: regenerate the polyglot fixture with every language, then bazel build and test it.

Usage: python3 tools/fixture_build.py --gazelle "$GAZELLE_BIN" [--bazel bazel] [--case fixtures/polyglot]
The scratch workspace is kept and its path printed, so you can inspect it after a failure.
'''
import argparse
import pathlib
import sys
import tempfile

from common import ROOT, gazelle_bin, run
import mutate  # reuses prepare_workspace and regenerate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gazelle')
    parser.add_argument('--bazel', default='bazel')
    parser.add_argument('--case', default=str(ROOT / 'fixtures' / 'polyglot'))
    args = parser.parse_args()
    args.golden_case, args.workspace = args.case, None  # shape expected by prepare_workspace
    gazelle = gazelle_bin(args.gazelle)
    ws = pathlib.Path(tempfile.mkdtemp(prefix='fixture-')) / 'ws'
    mutate.prepare_workspace(args, ws)
    print('scratch workspace: ' + str(ws))
    mutate.regenerate(gazelle, ws, [])  # no -lang restriction: all languages in the binary run
    code, _ = run([args.bazel, 'build', '//...'], cwd=ws, check=False)
    if code == 0:
        code, _ = run([args.bazel, 'test', '//...'], cwd=ws, check=False)
    print('fixture build: ' + ('PASS' if code == 0 else 'FAIL'))
    return 0 if code == 0 else 1


if __name__ == '__main__':
    sys.exit(main())