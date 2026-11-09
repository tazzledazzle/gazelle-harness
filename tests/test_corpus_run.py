import argparse
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import corpus_fetch  # noqa: E402
import corpus_run  # noqa: E402
from support import EnvPatch, make_fake_bazel, make_fake_gazelle  # noqa: E402

NL = chr(10)


def entry(**overrides):
    base = {'id': 'demo', 'language': 'go', 'gazelle_args': [], 'gazelle_directives': ['# gazelle:prefix example.com/demo'],
            'targets': ['//...'], 'bazel_version': ''}
    base.update(overrides)
    return base


class CorpusRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = pathlib.Path(self.tmp.name)
        self.out_root = self.base_dir / 'corpus_out'
        patcher = mock.patch.object(corpus_fetch, 'OUT_ROOT', self.out_root)  # keep every file inside the temp dir
        patcher.start()
        self.addCleanup(patcher.stop)
        self.gazelle = make_fake_gazelle(self.base_dir)
        self.bazel = make_fake_bazel(self.base_dir)
        self.tree = self.out_root / 'demo' / 'tree'  # what corpus_fetch would have produced
        (self.tree / 'a').mkdir(parents=True)
        (self.tree / 'a' / 'a.go').write_text('package a' + NL)

    def args(self, **overrides):
        values = dict(no_fetch=True, use_upstream=False, gazelle=self.gazelle, bazel=self.bazel,
                      skip_tests=False, depdiff=False)
        values.update(overrides)
        return argparse.Namespace(**values)

    def run_one(self, e=None, **arg_overrides):
        with contextlib.redirect_stdout(io.StringIO()):
            return corpus_run.run_one(e or entry(), {}, self.args(**arg_overrides))

    def saved(self):
        return json.loads((self.out_root / 'demo' / 'results.json').read_text())

    # prepare_workspace
    def test_prepare_workspace_creates_root_build_with_directives(self):
        work = corpus_run.prepare_workspace(entry(), self.out_root / 'demo')
        self.assertEqual((work / 'BUILD.bazel').read_text(), '# gazelle:prefix example.com/demo' + NL)

    def test_prepare_workspace_prepends_to_existing_root_build(self):
        (self.tree / 'BUILD').write_text('existing()' + NL)  # an existing BUILD must not be shadowed by a new BUILD.bazel
        work = corpus_run.prepare_workspace(entry(), self.out_root / 'demo')
        self.assertEqual((work / 'BUILD').read_text(), '# gazelle:prefix example.com/demo' + NL + 'existing()' + NL)
        self.assertFalse((work / 'BUILD.bazel').exists())

    def test_prepare_workspace_writes_bazel_version_and_starts_fresh(self):
        base = self.out_root / 'demo'
        (base / 'work').mkdir()
        (base / 'work' / 'stale.txt').write_text('old')
        work = corpus_run.prepare_workspace(entry(bazel_version='7.1.0'), base)
        self.assertEqual((work / '.bazelversion').read_text(), '7.1.0' + NL)
        self.assertFalse((work / 'stale.txt').exists())

    def test_count_errors_counts_only_line_starts(self):
        log = self.base_dir / 'b.log'
        log.write_text('ERROR: one' + NL + 'note: ERROR: not counted' + NL + 'ERROR: two' + NL)
        self.assertEqual(corpus_run.count_errors(log), 2)

    # run_one pipeline
    def test_green_run_records_every_stage(self):
        result = self.run_one()
        self.assertTrue(result['passed'])
        self.assertEqual([k for k in ('gazelle', 'build', 'test') if k in self.saved()], ['gazelle', 'build', 'test'])
        self.assertTrue((self.out_root / 'demo' / 'work' / 'a' / 'BUILD.bazel').exists())  # gazelle really ran in work/

    def test_gazelle_failure_skips_build_and_test(self):
        with EnvPatch(FAKE_GAZELLE_MODE='fail'):
            result = self.run_one()
        self.assertFalse(result['passed'])
        self.assertEqual(self.saved()['gazelle']['exit'], 3)
        self.assertNotIn('build', self.saved())

    def test_build_failure_skips_tests_and_counts_errors(self):
        with EnvPatch(FAKE_BAZEL_BUILD_EXIT='1'):
            result = self.run_one()
        self.assertFalse(result['passed'])
        self.assertEqual(self.saved()['build']['errors'], 2)
        self.assertNotIn('test', self.saved())

    def test_test_failure_fails_the_run(self):
        with EnvPatch(FAKE_BAZEL_TEST_EXIT='3'):
            result = self.run_one()
        self.assertFalse(result['passed'])
        self.assertEqual(self.saved()['test']['exit'], 3)

    def test_skip_tests_stops_after_build(self):
        result = self.run_one(skip_tests=True)
        self.assertTrue(result['passed'])
        self.assertNotIn('test', self.saved())

    def test_no_targets_means_gazelle_only(self):
        result = self.run_one(entry(targets=[]))
        self.assertTrue(result['passed'])
        self.assertNotIn('build', self.saved())

    def test_depdiff_runs_only_after_a_green_pipeline(self):
        with mock.patch('depdiff.compare_corpus', return_value={'missing': 0, 'extra_rate': 0.0}) as compare:
            self.run_one(depdiff=True)
            self.assertEqual(compare.call_count, 1)
            self.assertEqual(self.saved()['depdiff']['missing'], 0)
            with EnvPatch(FAKE_BAZEL_BUILD_EXIT='1'):
                self.run_one(depdiff=True)
            self.assertEqual(compare.call_count, 1)  # not called again for the red run

    def test_gazelle_args_reach_the_binary(self):
        argv_log = self.base_dir / 'argv.txt'
        recorder = self.base_dir / 'recorder'
        recorder.write_text('#!/bin/sh' + NL + 'echo "$@" > ' + str(argv_log) + NL)
        recorder.chmod(0o755)
        self.run_one(entry(gazelle_args=['-lang=go'], targets=[]), gazelle=str(recorder))
        self.assertIn('-lang=go', argv_log.read_text())
        self.assertIn('-repo_root=', argv_log.read_text())

    # main
    def test_main_exit_code_follows_results_and_unknown_id_fails(self):
        manifest = self.base_dir / 'manifest.json'
        manifest.write_text(json.dumps({'repos': [entry()]}))
        base_argv = ['corpus_run.py', '--manifest', str(manifest), '--gazelle', self.gazelle, '--bazel', self.bazel, '--no-fetch']
        with mock.patch.object(sys, 'argv', base_argv + ['--id', 'demo']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(corpus_run.main(), 0)
            with EnvPatch(FAKE_BAZEL_BUILD_EXIT='1'):
                self.assertEqual(corpus_run.main(), 1)
        with mock.patch.object(sys, 'argv', base_argv + ['--id', 'nope']), self.assertRaises(SystemExit):
            corpus_run.main()


if __name__ == '__main__':
    unittest.main()
