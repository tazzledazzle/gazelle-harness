import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import gate  # noqa: E402


class GateTest(unittest.TestCase):
    def test_c1_pass_and_fail(self):
        limits = {'max_missing_edges': 0, 'max_extra_rate': 0.02}
        good = {'id': 'x', 'depdiff': {'missing': 0, 'extra_rate': 0.01}}
        bad = {'id': 'y', 'depdiff': {'missing': 2, 'extra_rate': 0.0}}
        self.assertEqual([r[0] for r in gate.check_c1(limits, [good, bad])], [True, False])

    def test_c2_regression_against_baseline(self):
        limits = {'max_noop_seconds': 10, 'max_one_file_seconds': 2, 'max_regression_pct': 15}
        phase = lambda v: {'p95': v}
        base = {'py-100': {'packages': 100, 'cold': phase(10), 'noop': phase(1), 'one_file': phase(1)}}
        slow = {'py-100': {'packages': 100, 'cold': phase(12), 'noop': phase(1), 'one_file': phase(1)}}
        rows = gate.check_c2(limits, slow, base)
        self.assertEqual([r[0] for r in rows], [False, True, True])  # cold is 20% slower than baseline


if __name__ == '__main__':
    unittest.main()