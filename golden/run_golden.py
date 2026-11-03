#!/usr/bin/env python3
'''Golden test runner for Gazelle extensions. See the case layout in the hand-off doc.'''
import argparse
import difflib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


def find_cases(cases_dir):
    # A case is any directory that contains an 'input' subdirectory
    return sorted(p.parent for p in pathlib.Path(cases_dir).rglob('input') if p.is_dir())


def materialize(case, scratch):
    '''Copy input/ into scratch, renaming BUILD.in to BUILD.bazel.'''
    src = case / 'input'
    for path in sorted(src.rglob('*')):
        dest = scratch / path.relative_to(src)
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        if path.name == 'BUILD.in':
            dest = dest.with_name('BUILD.bazel')  # tests ship BUILD.in; Gazelle reads BUILD.bazel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)  # copy2 follows Bazel runfiles symlinks and keeps modes


def run_gazelle(gazelle, scratch, extra):
    # Default mode is fix/update; -repo_root pins the root so no WORKSPACE file is needed
    cmd = [gazelle, '-repo_root=' + str(scratch)] + extra
    return subprocess.run(cmd, cwd=scratch, capture_output=True, text=True)


def collect_builds(root):
    '''Map expected-file name (BUILD.out path) -> text for every generated BUILD.bazel.'''
    out = {}
    for path in sorted(root.rglob('BUILD.bazel')):
        out[str(path.relative_to(root).with_name('BUILD.out'))] = path.read_text()
    return out


def collect_expected(root):
    out = {}
    if root.exists():
        for path in sorted(root.rglob('BUILD.out')):
            out[str(path.relative_to(root))] = path.read_text()
    return out


def read_args(case):
    f = case / 'arguments.txt'
    return [line for line in f.read_text().splitlines() if line.strip()] if f.exists() else []


def diff_text(name, want, got):
    return ''.join(difflib.unified_diff(want.splitlines(True), got.splitlines(True), 'expected/' + name, 'actual/' + name))


def check_case(gazelle, case, update):
    '''Return a list of failure messages; an empty list means the case passed.'''
    with tempfile.TemporaryDirectory() as tmp:
        scratch = pathlib.Path(tmp)
        materialize(case, scratch)
        first = run_gazelle(gazelle, scratch, read_args(case))
        if first.returncode != 0:
            return ['gazelle exited ' + str(first.returncode) + ': ' + first.stderr]
        got = collect_builds(scratch)
        if update:  # --update rewrites the expectations from the actual output; review the git diff
            exp_root = case / 'expected'
            if exp_root.exists():
                shutil.rmtree(exp_root)
            for name, text in got.items():
                target = exp_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            return []
        failures = []
        want = collect_expected(case / 'expected')
        for name in sorted(set(want) | set(got)):
            if name not in got:
                failures.append('missing generated file: ' + name)
            elif name not in want:
                failures.append('unexpected generated file: ' + name)
            elif want[name] != got[name]:
                failures.append('content differs: ' + name + chr(10) + diff_text(name, want[name], got[name]))
        # Idempotence: running again on its own output must change nothing
        second = run_gazelle(gazelle, scratch, read_args(case))
        if second.returncode == 0 and collect_builds(scratch) != got:
            failures.append('second run changed the output (not idempotent)')
        return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gazelle', required=True)
    parser.add_argument('--cases-dir', required=True)
    parser.add_argument('--filter', default='')  # only cases whose path contains this text
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    gazelle = os.path.abspath(args.gazelle)  # make absolute before any directory change
    cases = [c for c in find_cases(args.cases_dir) if args.filter in str(c)]
    if not cases:
        print('no cases found under ' + args.cases_dir)
        return 1
    failed = 0
    for case in cases:
        problems = check_case(gazelle, case, args.update)
        status = 'UPDATED' if args.update else ('FAIL' if problems else 'ok')
        print(status + '  ' + str(case))
        for problem in problems:
            print('    ' + problem.replace(chr(10), chr(10) + '    '))
        failed += 1 if problems else 0
    print(str(len(cases) - failed) + '/' + str(len(cases)) + ' passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())