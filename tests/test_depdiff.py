import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import depdiff  # noqa: E402


def rule(name, kind, deps):
    """One line of Bazel query --output=streamed_jsonproto, built with json.dumps."""
    return json.dumps({'type': 'RULE', 'rule': {'name': name, 'ruleClass': kind,
                                                'attribute': [{'name': 'deps', 'stringListValue': deps}]}})


class DepDiffTest(unittest.TestCase):
    def test_package_level_comparison(self):
        original = depdiff.edges_from_lines([rule('//a:a', 'java_library', ['//b:b', '@maven//:guava'])])
        generated = depdiff.edges_from_lines([rule('//a:a_lib', 'java_library', ['//b:b_lib'])])
        result = depdiff.compare_edges(original, generated)
        self.assertEqual(result['missing'], 1)  # the guava edge was lost
        self.assertEqual(result['extra'], 0)  # renamed targets in the same packages are not extra

    def test_ignores_same_package_edges_and_other_kinds(self):
        lines = [rule('//a:a', 'java_library', ['//a:other']), rule('//a:g', 'genrule', ['//b:b'])]
        self.assertEqual(depdiff.edges_from_lines(lines), set())


if __name__ == '__main__':
    unittest.main()