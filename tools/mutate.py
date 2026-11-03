#!/usr/bin/env python3
'''C3: hand edits must survive regeneration. Mutates generated BUILD files, reruns Gazelle, checks the outcome.

Usage:
  python3 tools/mutate.py --golden-case golden/cases/go/basic --gazelle "$GAZELLE_BIN"
  python3 tools/mutate.py --workspace .corpus/dagger/work --gazelle "$GAZELLE_BIN" -- -lang=java
Arguments after -- are passed to Gazelle.
Writes bench_results/mutations.json for the gate.
'''
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from common import ROOT, gazelle_bin, load_json, save_json

Q = chr(34)  # a double quote, as a constant so the source stays readable
RULE_START = re.compile('^[A-Za-z_]+[(]$')  # a rule begins with kind( at column 0
SKIP_KINDS = {'load', 'package'}  # multi-line load( and package( blocks are not rules


def find_rules(text):
    '''Return (lines, rules); each rule is {kind, name, start, end} with line indexes.'''
    lines = text.splitlines()
    rules = []
    i = 0
    while i < len(lines):
        if RULE_START.match(lines[i]) and lines[i][:-1] not in SKIP_KINDS:
            j = i
            while j < len(lines) and lines[j] != ')':  # a rule ends at a ) in column 0
                j += 1
            name = ''
            for line in lines[i:j]:
                if line.strip().startswith('name ='):
                    name = line.split('=', 1)[1].strip().rstrip(',').strip(Q + chr(39))
                    break
            rules.append({'kind': lines[i][:-1], 'name': name, 'start': i, 'end': j})
            i = j
        i += 1
    return lines, rules


def apply_mutation(text, mutation):
    '''Return (new_text, marker); marker must appear after regeneration when expect is survives.'''
    lines, rules = find_rules(text)
    rule = rules[0]
    name_line = next(i for i in range(rule['start'], rule['end']) if lines[i].strip().startswith('name ='))
    op = mutation['op']
    marker = None
    if op == 'add_attr':
        lines.insert(name_line + 1, '    ' + mutation['attr'])
        marker = mutation['attr']
    elif op == 'add_keep':
        keep = '        ' + Q + '//keep:me' + Q + ',  # keep'  # Gazelle preserves entries marked keep
        deps = next((i for i in range(rule['start'], rule['end']) if lines[i].strip().startswith('deps = [')), None)
        if deps is not None:
            lines.insert(deps + 1, keep)
        else:
            lines[name_line + 1:name_line + 1] = ['    deps = [', keep, '    ],']
        marker = '//keep:me'
    elif op == 'delete_target':
        del lines[rule['start']:rule['end'] + 1]
    else:
        raise SystemExit('unknown mutation op: ' + op)
    return chr(10).join(lines) + chr(10), marker


def read_builds(root):
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob('BUILD.bazel'))}


def write_builds(root, files):
    for rel, text in files.items():
        (root / rel).write_text(text)


def regenerate(gazelle, root, extra):
    proc = subprocess.run([gazelle, '-repo_root=' + str(root)] + extra, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit('gazelle failed: ' + proc.stderr)


def prepare_workspace(args, root):
    '''Create root from a golden case input or from a copy of a workspace directory.'''
    if args.golden_case:
        sys.path.insert(0, str(ROOT / 'golden'))
        import run_golden
        root.mkdir()
        run_golden.materialize(pathlib.Path(args.golden_case), root)
    else:
        shutil.copytree(args.workspace, root, symlinks=True)


def split_extra(argv):
    '''Split argv at -- into (our arguments, Gazelle arguments).'''
    if '--' in argv:
        i = argv.index('--')
        return argv[:i], argv[i + 1:]
    return argv, []


def main():
    argv, extra = split_extra(sys.argv[1:])
    parser = argparse.ArgumentParser()
    parser.add_argument('--golden-case')
    parser.add_argument('--workspace')
    parser.add_argument('--gazelle')
    parser.add_argument('--mutations', default=str(ROOT / 'mutations.json'))
    args = parser.parse_args(argv)
    if bool(args.golden_case) == bool(args.workspace):
        parser.error('give exactly one of --golden-case or --workspace')
    gazelle = gazelle_bin(args.gazelle)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / 'ws'
        prepare_workspace(args, root)
        regenerate(gazelle, root, extra)  # first run produces the baseline
        baseline = read_builds(root)
        target = next((p for p in sorted(baseline) if find_rules(baseline[p])[1]), None)
        if target is None:
            raise SystemExit('no generated BUILD file contains a rule to mutate')
        for mutation in load_json(args.mutations)['mutations']:
            write_builds(root, baseline)  # reset every BUILD file to the baseline
            mutated, marker = apply_mutation(baseline[target], mutation)
            (root / target).write_text(mutated)
            regenerate(gazelle, root, extra)
            after = (root / target).read_text()
            ok = (marker in after) if mutation['expect'] == 'survives' else (after == baseline[target])
            results.append({'name': mutation['name'], 'ok': ok, 'target': target})
            print(('ok    ' if ok else 'FAIL  ') + mutation['name'])
    failures = sum(1 for r in results if not r['ok'])
    save_json(ROOT / 'bench_results' / 'mutations.json', {'failures': failures, 'results': results})
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())