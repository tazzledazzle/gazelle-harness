import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'golden'))
import run_golden  # noqa: E402
from support import EnvPatch, make_fake_gazelle  # noqa: E402

DEFAULT_EXPECTED = 'go_library(name = "a")' + chr(10)


def make_case(base, expected=DEFAULT_EXPECTED, args=None):
    """A case with one Go package a; the fake gazelle should generate a/BUILD.bazel for it."""
    case = pathlib.Path(base) / 'case'
    (case / 'input' / 'a').mkdir(parents=True)
    (case / 'input' / 'a' / 'a.go').write_text('package a' + chr(10))
    if expected is not None:
        (case / 'expected' / 'a').mkdir(parents=True)
        (case / 'expected' / 'a' / 'BUILD.out').write_text(expected)
    if args:
        (case / 'arguments.txt').write_text(chr(10).join(args) + chr(10))
    return case


class GoldenRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.gazelle = make_fake_gazelle(self.base)

    def test_find_cases_finds_directories_with_input(self):
        make_case(self.base)
        self.assertEqual(run_golden.find_cases(self.base), [self.base / 'case'])

    def test_materialize_renames_build_in(self):
        case = make_case(self.base)
        (case / 'input' / 'BUILD.in').write_text('# hand written' + chr(10))
        scratch = self.base / 'scratch'
        scratch.mkdir()
        run_golden.materialize(case, scratch)
        self.assertTrue((scratch / 'BUILD.bazel').exists())
        self.assertFalse((scratch / 'BUILD.in').exists())

    def test_read_args_skips_blank_lines(self):
        case = make_case(self.base, args=['-lang=go', '', '-r=false'])
        self.assertEqual(run_golden.read_args(case), ['-lang=go', '-r=false'])
        self.assertEqual(run_golden.read_args(self.base), [])  # no arguments.txt

    def test_matching_case_passes(self):
        self.assertEqual(run_golden.check_case(self.gazelle, make_case(self.base), update=False), [])

    def test_content_difference_is_reported_with_a_diff(self):
        case = make_case(self.base, expected='go_library(name = "wrong")' + chr(10))
        failures = run_golden.check_case(self.gazelle, case, update=False)
        self.assertEqual(len(failures), 1)
        self.assertIn('content differs: a/BUILD.out', failures[0])
        self.assertIn('-go_library(name = "wrong")', failures[0])

    def test_missing_expected_file_is_reported(self):
        failures = run_golden.check_case(self.gazelle, make_case(self.base, expected=None), update=False)
        self.assertEqual(failures, ['unexpected generated file: a/BUILD.out'])

    def test_unexpected_generated_file_is_reported(self):
        with EnvPatch(FAKE_GAZELLE_MODE='extra'):
            failures = run_golden.check_case(self.gazelle, make_case(self.base), update=False)
        self.assertTrue(any('unexpected generated file: BUILD.out' in f for f in failures))

    def test_missing_generated_file_is_reported(self):
        case = make_case(self.base)
        (case / 'expected' / 'b').mkdir()
        (case / 'expected' / 'b' / 'BUILD.out').write_text('x' + chr(10))
        failures = run_golden.check_case(self.gazelle, case, update=False)
        self.assertEqual(failures, ['missing generated file: b/BUILD.out'])

    def test_gazelle_crash_is_a_failure(self):
        with EnvPatch(FAKE_GAZELLE_MODE='fail'):
            failures = run_golden.check_case(self.gazelle, make_case(self.base), update=False)
        self.assertEqual(len(failures), 1)
        self.assertIn('gazelle exited 3', failures[0])

    def test_non_idempotent_output_is_a_failure(self):
        case = make_case(self.base, expected='# run' + chr(10))  # first run output matches; second run must not
        with EnvPatch(FAKE_GAZELLE_MODE='nonidempotent'):
            failures = run_golden.check_case(self.gazelle, case, update=False)
        self.assertEqual(failures, ['second run changed the output (not idempotent)'])

    def test_update_rewrites_expectations(self):
        case = make_case(self.base, expected='stale' + chr(10))
        self.assertEqual(run_golden.check_case(self.gazelle, case, update=True), [])
        self.assertEqual((case / 'expected' / 'a' / 'BUILD.out').read_text(), 'go_library(name = "a")' + chr(10))

    def test_update_refuses_to_record_non_idempotent_output(self):
        case = make_case(self.base, expected='old' + chr(10))
        with EnvPatch(FAKE_GAZELLE_MODE='nonidempotent'):
            failures = run_golden.check_case(self.gazelle, case, update=True)
        self.assertEqual(failures, ['second run changed the output (not idempotent)'])
        self.assertEqual((case / 'expected' / 'a' / 'BUILD.out').read_text(), 'old' + chr(10))  # untouched

    def run_main(self, *argv):
        old, sys.argv = sys.argv, ['run_golden.py'] + list(argv)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                return run_golden.main(), out.getvalue()
        finally:
            sys.argv = old

    def test_main_exit_codes(self):
        make_case(self.base)
        code, out = self.run_main('--gazelle', self.gazelle, '--cases-dir', str(self.base))
        self.assertEqual((code, '1/1 passed' in out), (0, True))
        with EnvPatch(FAKE_GAZELLE_MODE='fail'):
            code, _ = self.run_main('--gazelle', self.gazelle, '--cases-dir', str(self.base))
        self.assertEqual(code, 1)

    def test_main_fails_when_no_cases_match(self):
        code, out = self.run_main('--gazelle', self.gazelle, '--cases-dir', str(self.base))
        self.assertEqual(code, 1)
        self.assertIn('no cases found', out)
        make_case(self.base)
        code, _ = self.run_main('--gazelle', self.gazelle, '--cases-dir', str(self.base), '--filter', 'nomatch')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
