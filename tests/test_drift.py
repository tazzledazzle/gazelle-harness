'''Positive and negative test for tools/gazelle_check.sh (needs GAZELLE_BIN).'''
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK = ROOT / 'tools' / 'gazelle_check.sh'


def make_workspace(tmp):
    '''A tiny Go workspace where package a has no BUILD file, so Gazelle has work to do.'''
    (tmp / 'BUILD.bazel').write_text('# gazelle:prefix example.com/drift' + chr(10))  # Go needs an import prefix
    (tmp / 'a').mkdir()
    (tmp / 'a' / 'a.go').write_text('package a' + chr(10))
    return tmp


def run_check(ws):
    return subprocess.run(['bash', str(CHECK), str(ws)], capture_output=True, text=True)


@unittest.skipUnless(os.environ.get('GAZELLE_BIN'), 'GAZELLE_BIN not set')
class DriftTest(unittest.TestCase):
    def test_stale_tree_fails(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_workspace(pathlib.Path(d))
            result = run_check(ws)
            # Missing BUILD file for package a must be reported as drift (exit 1)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_workspace(pathlib.Path(d))
            # Generate the BUILD files for real, then the check must find nothing to change
            subprocess.run([os.environ['GAZELLE_BIN'], '-repo_root=' + str(ws)], cwd=ws, check=True)
            result = run_check(ws)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()