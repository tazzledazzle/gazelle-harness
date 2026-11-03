#!/usr/bin/env python3
'''Turn measurements into pass/fail using thresholds.json.

Usage: python3 tools/gate.py [--corpus-glob '.corpus/*/results.json'] [--bench bench_results/bench.json]
                             [--baseline bench_results/baseline.json] [--mutations bench_results/mutations.json]
'''
import argparse
import glob
import pathlib
import sys

from common import ROOT, load_json


def load_optional(path):
    return load_json(path) if path and pathlib.Path(path).exists() else None


def check_c1(limits, corpus_results):
    rows = []
    for r in corpus_results:
        d = r.get('depdiff')
        if not d:
            continue  # this run did not compute a dependency diff
        ok = d['missing'] <= limits['max_missing_edges'] and d['extra_rate'] <= limits['max_extra_rate']
        rows.append((ok, 'C1', r['id'] + ': missing=' + str(d['missing']) + ' extra_rate=' + str(round(d['extra_rate'], 4))))
    return rows


def check_c2(limits, bench, baseline):
    rows = []
    for key, entry in sorted((bench or {}).items()):
        if entry['packages'] >= 10000:  # absolute limits only make sense at the target scale
            ok = entry['noop']['p95'] <= limits['max_noop_seconds'] and entry['one_file']['p95'] <= limits['max_one_file_seconds']
            rows.append((ok, 'C2', key + ': noop=' + str(entry['noop']['p95']) + 's one_file=' + str(entry['one_file']['p95']) + 's'))
        base = (baseline or {}).get(key)
        if base:  # regression check against the stored baseline
            for phase in ('cold', 'noop', 'one_file'):
                allowed = base[phase]['p95'] * (1 + limits['max_regression_pct'] / 100)
                ok = entry[phase]['p95'] <= allowed
                rows.append((ok, 'C2', key + ' ' + phase + ': ' + str(entry[phase]['p95']) + 's, limit ' + str(round(allowed, 2)) + 's'))
    return rows


def check_c3(limits, mutations):
    if not mutations:
        return []
    failures = mutations['failures']
    return [(failures <= limits['max_mutation_failures'], 'C3', 'mutation failures=' + str(failures))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--thresholds', default=str(ROOT / 'thresholds.json'))
    parser.add_argument('--corpus-glob', default=str(ROOT / '.corpus' / '*' / 'results.json'))
    parser.add_argument('--bench', default=str(ROOT / 'bench_results' / 'bench.json'))
    parser.add_argument('--baseline', default=str(ROOT / 'bench_results' / 'baseline.json'))
    parser.add_argument('--mutations', default=str(ROOT / 'bench_results' / 'mutations.json'))
    args = parser.parse_args()
    limits = load_json(args.thresholds)
    corpus = [load_json(p) for p in sorted(glob.glob(args.corpus_glob))]
    rows = (check_c1(limits['C1'], corpus)
            + check_c2(limits['C2'], load_optional(args.bench), load_optional(args.baseline))
            + check_c3(limits['C3'], load_optional(args.mutations)))
    for ok, criterion, detail in rows:
        print(('PASS' if ok else 'FAIL') + '  ' + criterion + '  ' + detail)
    if not rows:
        print('no measurements found')
        return 1
    return 0 if all(ok for ok, _, _ in rows) else 1


if __name__ == '__main__':
    sys.exit(main())