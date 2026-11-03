#!/usr/bin/env python3
"""H7: time Gazelle on synthetic repos (cold, no-op, one-file-change); p95 over several runs.

Usage:
  python3 tools/bench.py --lang python --packages 1000 --gazelle "$GAZELLE_BIN" [--runs 5] [--baseline] [-- extra gazelle args]
Writes bench_results/bench.json (entries keyed <lang>-<packages>); --baseline also stores baseline.json.
If an extension prints a line starting with 'gazelle-stats ' (key=value pairs) to stderr when GAZELLE_STATS=1,
the last such line is recorded as stats (for example parser invocations).
"""
import argparse
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

from common import ROOT, gazelle_bin, load_json, save_json
import synth


def p95(values):
    ordered = sorted(values)
    return round(ordered[max(math.ceil(0.95 * len(ordered)) - 1, 0)], 3)


def measured_run(cmd, cwd):
    """Run cmd once; return (seconds, peak_rss_mb, stats). wait4 gives this child its own resource usage."""
    err_file = tempfile.TemporaryFile()
    env = {**os.environ, 'GAZELLE_STATS': '1'}
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=err_file)
    _, status, usage = os.wait4(proc.pid, 0)
    seconds = time.perf_counter() - start
    proc.returncode = os.waitstatus_to_exitcode(status)  # we reaped it ourselves, so tell Popen
    err_file.seek(0)
    text = err_file.read().decode('utf-8', errors='replace')
    if proc.returncode != 0:
        raise SystemExit('gazelle failed: ' + text[-2000:])
    rss_mb = usage.ru_maxrss / (1024 * 1024) if sys.platform == 'darwin' else usage.ru_maxrss / 1024  # macOS reports bytes
    stats = {}
    for line in text.splitlines():
        if line.startswith('gazelle-stats '):
            for pair in line.split()[1:]:
                key, _, value = pair.partition('=')
                stats[key] = value
    return seconds, rss_mb, stats


def bench(lang, packages, gazelle, runs, extra, fanout=3, seed=1):
    flags = extra if any(a.startswith('-lang') for a in extra) else ['-lang=' + synth.LANG_FLAG[lang]] + extra
    peak, stats = 0.0, {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        pristine = tmp / 'pristine'
        synth.generate(lang, pristine, packages, fanout, seed)

        def cmd(workspace):
            return [gazelle, '-repo_root=' + str(workspace)] + flags

        def timed(workspace):
            nonlocal peak, stats
            seconds, rss, run_stats = measured_run(cmd(workspace), workspace)
            peak, stats = max(peak, rss), run_stats or stats
            return seconds

        cold = []
        for _ in range(runs):  # cold = BUILD files do not exist yet, fresh copy each time
            ws = tmp / 'cold'
            shutil.rmtree(ws, ignore_errors=True)
            shutil.copytree(pristine, ws)
            cold.append(timed(ws))
        ws = tmp / 'warm'  # no-op and one-file runs start from an already generated tree
        shutil.copytree(pristine, ws)
        timed(ws)  # warm-up run generates the BUILD files; not recorded
        noop = [timed(ws) for _ in range(runs)]
        one_file = []
        for k in range(runs):
            synth.touch(ws, lang, k)
            one_file.append(timed(ws))
    return {'lang': lang, 'packages': packages, 'runs': runs, 'peak_rss_mb': round(peak, 1), 'stats': stats,
            'cold': {'p95': p95(cold), 'runs': [round(v, 3) for v in cold]},
            'noop': {'p95': p95(noop), 'runs': [round(v, 3) for v in noop]},
            'one_file': {'p95': p95(one_file), 'runs': [round(v, 3) for v in one_file]}}


def merge_save(path, key, entry):
    data = load_json(path) if pathlib.Path(path).exists() else {}
    data[key] = entry
    save_json(path, data)


def main():
    argv = sys.argv[1:]
    extra = argv[argv.index('--') + 1:] if '--' in argv else []
    argv = argv[:argv.index('--')] if '--' in argv else argv
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', required=True, choices=sorted(synth.GENERATORS))
    parser.add_argument('--packages', type=int, required=True)
    parser.add_argument('--gazelle')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args(argv)
    entry = bench(args.lang, args.packages, gazelle_bin(args.gazelle), args.runs, extra)
    key = args.lang + '-' + str(args.packages)
    merge_save(ROOT / 'bench_results' / 'bench.json', key, entry)
    if args.baseline:
        merge_save(ROOT / 'bench_results' / 'baseline.json', key, entry)
    print(key + ': cold p95=' + str(entry['cold']['p95']) + 's noop p95=' + str(entry['noop']['p95'])
          + 's one_file p95=' + str(entry['one_file']['p95']) + 's peak=' + str(entry['peak_rss_mb']) + 'MB')


if __name__ == '__main__':
    main()