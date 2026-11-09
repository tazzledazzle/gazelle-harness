import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import mutate  # noqa: E402

Q = chr(34)
SAMPLE = chr(10).join([
    'load(' + Q + '@x//:y.bzl' + Q + ', ' + Q + 'go_library' + Q + ')',
    '',
    'go_library(',
    '    name = ' + Q + 'a' + Q + ',',
    '    srcs = [' + Q + 'a.go' + Q + '],',
    ')',
    '',
    ])


class MutateTest(unittest.TestCase):
    def test_find_rules_skips_load(self):
        _, rules = mutate.find_rules(SAMPLE)
        self.assertEqual([(r['kind'], r['name']) for r in rules], [('go_library', 'a')])

    def test_add_attr_goes_after_name(self):
        text, marker = mutate.apply_mutation(SAMPLE, {'op': 'add_attr', 'attr': 'tags = [],'})
        self.assertIn('    name = ' + Q + 'a' + Q + ',' + chr(10) + '    tags = [],', text)
        self.assertEqual(marker, 'tags = [],')

    def test_add_keep_creates_deps(self):
        text, marker = mutate.apply_mutation(SAMPLE, {'op': 'add_keep'})
        self.assertIn('# keep', text)
        self.assertIn('deps = [', text)

    def test_delete_target_removes_rule(self):
        text, _ = mutate.apply_mutation(SAMPLE, {'op': 'delete_target'})
        self.assertNotIn('go_library(', text)


if __name__ == '__main__':
    unittest.main()
