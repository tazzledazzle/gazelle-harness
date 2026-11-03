"""Unit test for corpus_fetch using a throwaway local git repository (no network, no Bazel)."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import corpus_fetch  # noqa: E402


def sh(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def make_upstream(path):
    """Create a git repo with BUILD files in a/ and b/ plus a MODULE.bazel; return the commit id."""
    path.mkdir()
    sh(['git', 'init', '-q'], path)
    (path / 'MODULE.bazel').write_text('module(name = "x")' + chr(10))
    for name in ('a', 'b'):
        (path / name).mkdir()
        (path / name / 'BUILD.bazel').write_text('# build' + chr(10))
    sh(['git', 'add', '-A'], path)
    sh(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', 'init'], path)
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=path, capture_output=True, text=True).stdout.strip()


class FetchTest(unittest.TestCase):
    def test_strip_and_keep(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            commit = make_upstream(tmp / 'upstream')
            corpus_fetch.OUT_ROOT = tmp / 'out'  # redirect outputs into the temp directory
            corpus_fetch.CACHE_ROOT = tmp / 'cache'
            entry = {'id': 't', 'upstream': str(tmp / 'upstream'), 'fork_repo': 't', 'commit': commit, 'strip_dirs': ['a']}
            base = corpus_fetch.fetch(entry, {'fork_owner': 'REPLACE_ME'}, use_upstream=True)
            tree = base / 'tree'
            self.assertFalse((tree / 'a' / 'BUILD.bazel').exists())  # matched strip_dirs: removed
            self.assertTrue((tree / 'b' / 'BUILD.bazel').exists())  # outside strip_dirs: kept
            self.assertTrue((tree / 'MODULE.bazel').exists())  # module files must be kept
            self.assertTrue((base / 'original_builds' / 'a' / 'BUILD.bazel').exists())  # original preserved


if __name__ == '__main__':
    unittest.main()