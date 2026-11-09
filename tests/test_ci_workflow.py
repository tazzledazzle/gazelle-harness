import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / '.github' / 'workflows').glob('*.yml'))
USES = re.compile(r'^\s*-?\s*uses:\s*(\S+)', re.MULTILINE)
FULL_SHA = re.compile(r'^[^@\s]+@[0-9a-f]{40}$')


class WorkflowPolicyTest(unittest.TestCase):
    """Supply-chain and hygiene rules for the workflows, enforced on every pull request."""

    def test_there_are_workflows(self):
        self.assertTrue(WORKFLOWS)

    def test_every_action_is_pinned_to_a_full_commit_sha(self):
        for path in WORKFLOWS:
            for ref in USES.findall(path.read_text()):
                if ref.startswith('./'):  # a local action lives in this repository
                    continue
                self.assertRegex(ref, FULL_SHA, path.name + ': pin ' + ref + ' to a 40-character commit SHA, not a tag')

    def test_every_job_has_a_timeout(self):
        for path in WORKFLOWS:
            text = path.read_text()
            jobs = re.split(r'^jobs:\s*$', text, flags=re.MULTILINE)[1]
            for name, body in re.findall(r'^  ([\w-]+):[^\n]*\n((?:    .*\n|\n)+)', jobs, flags=re.MULTILINE):
                self.assertIn('timeout-minutes:', body, path.name + ': job ' + name + ' has no timeout-minutes')

    def test_default_token_is_read_only(self):
        for path in WORKFLOWS:
            self.assertRegex(path.read_text(), r'(?m)^permissions:\s*\n\s+contents:\s*read\s*$', path.name)

    def test_checkout_does_not_persist_credentials(self):
        for path in WORKFLOWS:
            text = path.read_text()
            self.assertEqual(text.count('actions/checkout@'), text.count('persist-credentials: false'), path.name)


if __name__ == '__main__':
    unittest.main()
