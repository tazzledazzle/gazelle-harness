import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import bench  # noqa: E402
import synth  # noqa: E402


def snapshot(root):
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob('*')) if p.is_file()}


class SynthTest(unittest.TestCase):
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = pathlib.Path(d) / 'a', pathlib.Path(d) / 'b'
            synth.generate('python', a, 20, fanout=3, seed=5)
            synth.generate('python', b, 20, fanout=3, seed=5)
            self.assertEqual(snapshot(a), snapshot(b))  # same seed, same repository

    def test_dag_without_cycles(self):
        deps = synth.make_deps(30, 4, 0.0, 1)
        self.assertTrue(all(j < i for i, row in enumerate(deps) for j in row))  # imports point only downward

    def test_cycles_add_back_edges(self):
        deps = synth.make_deps(30, 2, 1.0, 1)
        self.assertTrue(any(j > i for i, row in enumerate(deps) for j in row))

    def test_p95(self):
        self.assertEqual(bench.p95([1, 2, 3, 4, 5]), 5)
        self.assertEqual(bench.p95([2.0]), 2.0)


if __name__ == '__main__':
    unittest.main()