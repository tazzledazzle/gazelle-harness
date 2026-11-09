import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import gate  # noqa: E402


class GateTest(unittest.TestCase):
    def test_c1_pass_and_fail(self):
        limits = {'max_missing_edges': 0, 'max_extra_rate': 0.02}
        good = {'id': 'x', 'passed': True, 'depdiff': {'missing': 0, 'extra_rate': 0.01}}
        bad = {'id': 'y', 'passed': True, 'depdiff': {'missing': 2, 'extra_rate': 0.0}}
        self.assertEqual([r[0] for r in gate.check_c1(limits, [good, bad])], [True, False])

    def test_c2_regression_against_baseline(self):
        limits = {'max_noop_seconds': 10, 'max_one_file_seconds': 2, 'max_regression_pct': 15,
                  'shared_runner_regression_pct': 50, 'regression_floor_seconds': 0.25}
        phase = lambda v: {'p95': v}
        base = {'py-100': {'packages': 100, 'cold': phase(10), 'noop': phase(1), 'one_file': phase(1)}}
        slow = {'py-100': {'packages': 100, 'cold': phase(12), 'noop': phase(1), 'one_file': phase(1)}}
        rows = gate.check_c2(limits, slow, base)
        self.assertEqual([r[0] for r in rows], [False, True, True])  # cold is 20% slower than baseline

    def test_c1_failed_corpus_run_fails_the_gate(self):
        limits = {'max_missing_edges': 0, 'max_extra_rate': 0.02}
        broken = {'id': 'z', 'passed': False, 'gazelle': {'exit': 0}, 'build': {'exit': 1}}  # no depdiff: build was red
        rows = gate.check_c1(limits, [broken])
        self.assertEqual([r[0] for r in rows], [False])
        self.assertIn('failed at build', rows[0][2])

    def test_c1_passed_run_without_depdiff_fails(self):
        rows = gate.check_c1({'max_missing_edges': 0, 'max_extra_rate': 0.02}, [{'id': 'q', 'passed': True}])
        self.assertEqual([r[0] for r in rows], [False])

    def test_c1_missing_result_for_expected_repo_fails(self):
        limits = {'max_missing_edges': 0, 'max_extra_rate': 0.02}
        good = {'id': 'x', 'passed': True, 'depdiff': {'missing': 0, 'extra_rate': 0.0}}
        rows = gate.check_c1(limits, [good], expected_ids=['x', 'never-ran'])
        self.assertEqual([(r[0], r[2].split(':')[0]) for r in rows], [(True, 'x'), (False, 'never-ran')])

    LIMITS = {'max_noop_seconds': 10, 'max_one_file_seconds': 2, 'max_regression_pct': 15,
              'shared_runner_regression_pct': 50, 'regression_floor_seconds': 0.25}

    @staticmethod
    def entry(cold, noop=1, one_file=1, packages=1000):
        phase = lambda v: {'p95': v}
        return {'packages': packages, 'cold': phase(cold), 'noop': phase(noop), 'one_file': phase(one_file)}

    def test_c2_shared_runner_tolerates_noise_that_dedicated_rejects(self):
        base = {'py-1000': self.entry(10)}
        slow = {'py-1000': self.entry(13)}  # 30% slower: over 15%, under 50%
        self.assertFalse(all(r[0] for r in gate.check_c2(self.LIMITS, slow, base)))
        self.assertTrue(all(r[0] for r in gate.check_c2(self.LIMITS, slow, base, shared_runner=True)))

    def test_c2_shared_runner_still_catches_a_real_regression(self):
        rows = gate.check_c2(self.LIMITS, {'py-1000': self.entry(16)}, {'py-1000': self.entry(10)}, shared_runner=True)
        self.assertFalse(all(r[0] for r in rows))  # 60% slower

    def test_c2_floor_ignores_millisecond_jitter(self):
        base = {'py-100': self.entry(0.008, 0.007, 0.007, packages=100)}
        jitter = {'py-100': self.entry(0.012, 0.011, 0.011, packages=100)}  # +50% but only a few ms
        self.assertTrue(all(r[0] for r in gate.check_c2(self.LIMITS, jitter, base)))

    def test_c2_missing_baseline_fails(self):
        rows = gate.check_c2(self.LIMITS, {'py-1000': self.entry(10)}, {})
        self.assertEqual([r[0] for r in rows], [False])
        self.assertIn('no baseline', rows[0][2])


class GateMainTest(unittest.TestCase):
    """Run the CLI end to end against temporary files."""

    def run_gate(self, corpus_results, require, bench=None):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / 'thresholds.json').write_text(json.dumps({
                'C1': {'max_missing_edges': 0, 'max_extra_rate': 0.02},
                'C2': {'max_noop_seconds': 10, 'max_one_file_seconds': 2, 'max_regression_pct': 15},
                'C3': {'max_mutation_failures': 0}}))
            (d / 'manifest.json').write_text(json.dumps({'repos': [{'id': 'a'}, {'id': 'b'}]}))
            for r in corpus_results:
                (d / ('corpus-' + r['id'])).mkdir()
                (d / ('corpus-' + r['id']) / 'results.json').write_text(json.dumps(r))
            argv = ['gate.py', '--thresholds', str(d / 'thresholds.json'), '--manifest', str(d / 'manifest.json'),
                    '--corpus-glob', str(d / 'corpus-*' / 'results.json'),
                    '--bench', str(d / 'none.json'), '--baseline', str(d / 'none.json'), '--mutations', str(d / 'none.json'),
                    '--require'] + require
            old, sys.argv = sys.argv, argv
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return gate.main()
            finally:
                sys.argv = old

    GOOD = {'passed': True, 'depdiff': {'missing': 0, 'extra_rate': 0.0}}

    def test_all_green_passes(self):
        results = [{'id': 'a', **self.GOOD}, {'id': 'b', **self.GOOD}]
        self.assertEqual(self.run_gate(results, ['C1']), 0)

    def test_one_repo_never_reporting_fails(self):
        self.assertEqual(self.run_gate([{'id': 'a', **self.GOOD}], ['C1']), 1)

    def test_one_red_repo_fails(self):
        results = [{'id': 'a', **self.GOOD}, {'id': 'b', 'passed': False, 'build': {'exit': 1}}]
        self.assertEqual(self.run_gate(results, ['C1']), 1)

    def test_required_c2_without_bench_fails(self):
        results = [{'id': 'a', **self.GOOD}, {'id': 'b', **self.GOOD}]
        self.assertEqual(self.run_gate(results, ['C1', 'C2']), 1)


if __name__ == '__main__':
    unittest.main()