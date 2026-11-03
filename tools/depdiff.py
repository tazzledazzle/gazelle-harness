#!/usr/bin/env python3
"""Compare package-level dependency edges between original and regenerated BUILD files.

Usage: python3 tools/depdiff.py --id dagger [--bazel bazel]
Needs .corpus/<id>/{tree,original_builds,work} from corpus_run.py.
"""
import argparse
import json
import shutil
import subprocess

import corpus_fetch
from common import save_json

DEP_ATTRS = {'deps', 'exports', 'runtime_deps'}  # attributes that express dependencies
KIND_WORDS = ('library', 'binary', 'test', 'project')  # rule kinds worth comparing (ts_project included)


def edge_target(label):
    label = label.replace('@@', '@')  # Bzlmod canonical names start with @@
    if label.startswith('//'):
        return label.split(':')[0]  # first-party: compare at package level
    return label  # external: compare the full label


def edges_from_lines(lines):
    """Parse streamed_jsonproto query lines into a set of (package, target) edges."""
    edges = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        target = json.loads(line)
        if target.get('type') != 'RULE':
            continue
        rule = target['rule']
        if not any(word in rule.get('ruleClass', '') for word in KIND_WORDS):
            continue
        source = rule['name'].split(':')[0]  # '//pkg:name' becomes '//pkg'
        for attr in rule.get('attribute', []):
            if attr.get('name') in DEP_ATTRS:
                for label in attr.get('stringListValue', []):
                    dest = edge_target(label)
                    if dest != source:  # ignore edges between targets of one package
                        edges.add((source, dest))
    return edges


def query_edges(workspace, bazel):
    cmd = [bazel, 'query', '//...', '--output=streamed_jsonproto', '--noimplicit_deps', '--notool_deps', '--keep_going']
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
    if proc.returncode not in (0, 3):  # 3 means partial results under --keep_going
        raise SystemExit('bazel query failed in ' + str(workspace) + ': ' + proc.stderr[-2000:])
    return edges_from_lines(proc.stdout.splitlines())


def compare_edges(original, generated):
    missing = original - generated
    extra = generated - original
    return {
        'original_edges': len(original),
        'generated_edges': len(generated),
        'missing': len(missing),
        'extra': len(extra),
        'extra_rate': len(extra) / max(len(generated), 1),
        'missing_sample': sorted(' -> '.join(e) for e in missing)[:20],
        'extra_sample': sorted(' -> '.join(e) for e in extra)[:20],
    }


def compare_corpus(repo_id, bazel):
    base = corpus_fetch.OUT_ROOT / repo_id
    original = base / 'original'
    if original.exists():
        shutil.rmtree(original)
    shutil.copytree(base / 'tree', original, symlinks=True)  # the stripped tree ...
    shutil.copytree(base / 'original_builds', original, dirs_exist_ok=True, symlinks=True)  # ... plus its original BUILD files
    result = compare_edges(query_edges(original, bazel), query_edges(base / 'work', bazel))
    save_json(base / 'depdiff.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True)
    parser.add_argument('--bazel', default='bazel')
    args = parser.parse_args()
    print(json.dumps(compare_corpus(args.id, args.bazel), indent=2))