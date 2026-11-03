#!/usr/bin/env python3
"""H6: directory-scoped runs in shuffled order must produce the same BUILD files as one whole-repo run.

Usage:
  python3 tools/check_order.py --golden-case golden/cases/go/basic --gazelle "$GAZELLE_BIN" [--seed 7]
  python3 tools/check_order.py --workspace .corpus/dagger/work --gazelle "$GAZELLE_BIN" -- -lang=java
"""
import argparse
import difflib
import pathlib
import random
import sys
import tempfile

from common import gazelle_bin
import mutate


def main():
    argv, extra = mutate.split_extra(sys.argv[1:])
    parser = argparse.ArgumentParser()
    parser.add_argument('--golden-case')
    parser.add_argument('--workspace')
    parser.add_argument('--gazelle')
    parser.add_argument('--seed', type=int, default=7)  # fixed seed so a failure can be reproduced
    args = parser.parse_args(argv)
    if bool(args.golden_case) == bool(args.workspace):
        parser.error('give exactly one of --golden-case or --workspace')
    gazelle = gazelle_bin(args.gazelle)
    with tempfile.TemporaryDirectory() as tmp:
        whole = pathlib.Path(tmp) / 'whole'
        scoped = pathlib.Path(tmp) / 'scoped'
        mutate.prepare_workspace(args, whole)
        mutate.prepare_workspace(args, scoped)
        mutate.regenerate(gazelle, whole, extra)  # reference: one run over everything
        expected = mutate.read_builds(whole)
        dirs = sorted({str(pathlib.Path(rel).parent) for rel in expected})  # '.' is the root
        random.Random(args.seed).shuffle(dirs)
        print('order: ' + ', '.join(dirs))
        for d in dirs:
            # -r=false stops recursion, so each run sees only the directory it was given
            mutate.regenerate(gazelle, scoped, ['-r=false'] + extra + [d])
        got = mutate.read_builds(scoped)
    problems = 0
    for rel in sorted(set(expected) | set(got)):
        if expected.get(rel) != got.get(rel):
            problems += 1
            print('DIFF ' + rel)
            print(''.join(difflib.unified_diff((expected.get(rel) or '').splitlines(True), (got.get(rel) or '').splitlines(True), 'whole/' + rel, 'scoped/' + rel)))
    print('same output' if not problems else str(problems) + ' files differ')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())