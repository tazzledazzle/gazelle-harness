import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class BazelrcTest(unittest.TestCase):
    def test_java_toolchain_is_pinned_for_target_and_exec(self):
        """Without these, a runner whose default JDK is newer than javac's JDK fails building protobuf's Java."""
        flags = {line.split(None, 1)[1].strip() for line in (ROOT / '.bazelrc').read_text().splitlines() if line.startswith('build ')}
        for flag in ('--java_language_version=21', '--java_runtime_version=remotejdk_21',
                     '--tool_java_language_version=21', '--tool_java_runtime_version=remotejdk_21'):
            self.assertIn(flag, flags)


if __name__ == '__main__':
    unittest.main()
