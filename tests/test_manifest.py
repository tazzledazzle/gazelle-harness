import copy
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import validate_manifest  # noqa: E402
from common import load_json  # noqa: E402

SHA = 'a' * 40


def good_manifest():
    entry = {'id': 'x', 'language': 'java', 'upstream': 'https://github.com/o/x', 'fork_repo': 'x', 'commit': SHA,
             'strip_dirs': ['*'], 'gazelle_args': [], 'gazelle_directives': [], 'targets': ['//...'],
             'bazel_version': '', 'notes': 'fine'}
    return {'fork_owner': 'me', 'repos': [entry]}


class ValidateManifestTest(unittest.TestCase):
    def test_good_manifest_has_no_errors(self):
        self.assertEqual(validate_manifest.validate(good_manifest()), [])

    def test_placeholder_fork_owner_fails(self):
        m = good_manifest()
        m['fork_owner'] = 'REPLACE_WITH_YOUR_GITHUB_ORG'
        self.assertTrue(any('fork_owner' in e for e in validate_manifest.validate(m)))

    def test_empty_or_short_commit_fails(self):
        for bad in ('', 'abc1234'):
            m = good_manifest()
            m['repos'][0]['commit'] = bad
            self.assertTrue(any('40-character' in e for e in validate_manifest.validate(m)), bad)

    def test_placeholder_in_strip_dirs_fails(self):
        m = good_manifest()
        m['repos'][0]['strip_dirs'] = ['REPLACE_AFTER_INSPECTING']
        self.assertTrue(any('placeholder' in e for e in validate_manifest.validate(m)))

    def test_duplicate_ids_fail(self):
        m = good_manifest()
        m['repos'].append(copy.deepcopy(m['repos'][0]))
        self.assertTrue(any('duplicate id' in e for e in validate_manifest.validate(m)))

    def test_missing_key_and_empty_targets_fail(self):
        m = good_manifest()
        del m['repos'][0]['notes']
        m['repos'][0]['targets'] = []
        errors = validate_manifest.validate(m)
        self.assertTrue(any('missing key notes' in e for e in errors))
        self.assertTrue(any('targets is empty' in e for e in errors))

    def test_shared_upstream_must_share_a_commit(self):
        m = good_manifest()
        second = copy.deepcopy(m['repos'][0])
        second.update(id='y', commit='b' * 40)
        m['repos'].append(second)
        self.assertTrue(any('different commits' in e for e in validate_manifest.validate(m)))

    def test_allow_unpinned_skips_pin_checks_only(self):
        m = good_manifest()
        m['fork_owner'] = 'REPLACE_ME'
        m['repos'][0]['commit'] = ''
        self.assertEqual(validate_manifest.validate(m, allow_unpinned=True), [])


class CommittedManifestTest(unittest.TestCase):
    """Guards the real files, so an unfinished manifest or a drifted CI matrix fails on the pull request."""

    def test_committed_manifest_is_complete(self):
        manifest = load_json(ROOT / 'corpus' / 'manifest.json')
        self.assertEqual(validate_manifest.validate(manifest), [])

    def test_ci_corpus_matrix_matches_manifest_ids(self):
        manifest_ids = {r['id'] for r in load_json(ROOT / 'corpus' / 'manifest.json')['repos']}
        ci = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text()
        match = re.search(r'repo:\s*\[([^\]]*)\]', ci)
        self.assertIsNotNone(match, 'no repo matrix found in ci.yml')
        matrix_ids = {i.strip() for i in match.group(1).split(',') if i.strip()}
        self.assertEqual(matrix_ids, manifest_ids)


if __name__ == '__main__':
    unittest.main()
