#!/usr/bin/env python3
"""Turn measurements into pass/fail using thresholds.json.

Usage: python3 tools/gate.py [--corpus-glob '.corpus/*/results.json'] [--bench bench_results/bench.json]
                             [--baseline bench_results/baseline.json] [--mutations bench_results/mutations.json]
                             [--manifest corpus/manifest.json] [--require C1 C2 C3] [--shared-runner]

A criterion listed in --require must produce at least one row, so a missing measurement fails the gate
instead of passing silently. C1 also fails for any corpus repo that failed to run or has no result file.
"""
import argparse
import glob
import pathlib
import sys

from common import ROOT, load_json


def load_optional(path):
    return load_json(path) if path and pathlib.Path(path).exists() else None


def failed_stage(result):
    """Name the first pipeline stage that failed in a corpus result, for the failure message."""
    for stage in ('gazelle', 'build', 'test'):
        if result.get(stage, {}).get('exit', 0) != 0:
            return stage
    return 'unknown'


def check_c1(limits, corpus_results, expected_ids=None):
    """One row per corpus repo: failed runs, missing results and missing dependency diffs all fail."""
    rows = []
    seen = set()
    for r in corpus_results:
        seen.add(r['id'])
        if not r.get('passed'):  # a red build or test is a failure even though it has no dependency diff
            rows.append((False, 'C1', r['id'] + ': corpus run failed at ' + failed_stage(r)))
            continue
        d = r.get('depdiff')
        if not d:  # the nightly run always passes --depdiff, so its absence means the check did not happen
            rows.append((False, 'C1', r['id'] + ': no dependency diff in results'))
            continue
        ok = d['missing'] <= limits['max_missing_edges'] and d['extra_rate'] <= limits['max_extra_rate']
        rows.append((ok, 'C1', r['id'] + ': missing=' + str(d['missing']) + ' extra_rate=' + str(round(d['extra_rate'], 4))))
    for missing_id in sorted(set(expected_ids or []) - seen):  # a repo that never reported is not a pass
        rows.append((False, 'C1', missing_id + ': no results file (job skipped, crashed or artifact missing)'))
    return rows


def check_c2(limits, bench, baseline, shared_runner=False):
    """Absolute limits at 10000+ packages, plus regression against the stored baseline.

    shared_runner widens the regression percentage because shared CI machines are noisy. A regression must
    also exceed regression_floor_seconds, so millisecond-scale timings cannot fail on jitter alone.
    """
    pct = limits['shared_runner_regression_pct'] if shared_runner else limits['max_regression_pct']
    floor = limits.get('regression_floor_seconds', 0)
    rows = []
    for key, entry in sorted((bench or {}).items()):
        if entry['packages'] >= 10000:  # absolute limits only make sense at the target scale
            ok = entry['noop']['p95'] <= limits['max_noop_seconds'] and entry['one_file']['p95'] <= limits['max_one_file_seconds']
            rows.append((ok, 'C2', key + ': noop=' + str(entry['noop']['p95']) + 's one_file=' + str(entry['one_file']['p95']) + 's'))
        base = (baseline or {}).get(key)
        if not base:  # without a baseline the regression check cannot run, and a skipped check must not look like a pass
            rows.append((False, 'C2', key + ': no baseline; record one with the bench workflow (record_baseline) and commit baseline.json'))
            continue
        for phase in ('cold', 'noop', 'one_file'):
            allowed = max(base[phase]['p95'] * (1 + pct / 100), base[phase]['p95'] + floor)
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
    parser.add_argument('--manifest', default=str(ROOT / 'corpus' / 'manifest.json'))  # source of expected corpus ids
    parser.add_argument('--shared-runner', action='store_true')  # benchmarks ran on a shared CI runner: wider tolerance
    parser.add_argument('--require', nargs='*', default=[], choices=['C1', 'C2', 'C3'])
    args = parser.parse_args()
    limits = load_json(args.thresholds)
    corpus = [load_json(p) for p in sorted(glob.glob(args.corpus_glob))]
    expected = [e['id'] for e in load_json(args.manifest)['repos']] if 'C1' in args.require else None
    rows = (check_c1(limits['C1'], corpus, expected)
            + check_c2(limits['C2'], load_optional(args.bench), load_optional(args.baseline), args.shared_runner)
            + check_c3(limits['C3'], load_optional(args.mutations)))
    for criterion in args.require:  # a required criterion with no rows means its measurements never arrived
        if not any(row[1] == criterion for row in rows):
            rows.append((False, criterion, 'required but no measurements found'))
    for ok, criterion, detail in rows:
        print(('PASS' if ok else 'FAIL') + '  ' + criterion + '  ' + detail)
    if not rows:
        print('no measurements found')
        return 1
    return 0 if all(ok for ok, _, _ in rows) else 1


if __name__ == '__main__':
    sys.exit(main())