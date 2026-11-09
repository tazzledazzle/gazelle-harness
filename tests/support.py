"""Fake gazelle and bazel executables so the runners can be tested without Bazel or network access."""
import os
import pathlib
import stat
import sys

FAKE_GAZELLE = '''#!{python}
import os, pathlib, sys
root = None
for arg in sys.argv[1:]:
    if arg.startswith('-repo_root='):
        root = pathlib.Path(arg.split('=', 1)[1])
mode = os.environ.get('FAKE_GAZELLE_MODE', 'ok')
if mode == 'fail':  # a gazelle crash
    print('boom', file=sys.stderr)
    sys.exit(3)
if mode == 'extra':  # writes a root BUILD file the case does not expect
    (root / 'BUILD.bazel').write_text('unexpected' + chr(10))
for d in sorted({{p.parent for p in root.rglob('*.go')}}):
    build = d / 'BUILD.bazel'
    if mode == 'nonidempotent':  # every run appends, so a second run differs from the first
        with open(build, 'a') as f:
            f.write('# run' + chr(10))
    elif not build.exists():  # ok: generate once, leave existing files alone (like a merge-safe gazelle)
        build.write_text('go_library(name = "' + d.name + '")' + chr(10))
'''

FAKE_BAZEL = '''#!{python}
import os, sys
verb = sys.argv[1]
code = int(os.environ.get('FAKE_BAZEL_' + verb.upper() + '_EXIT', '0'))
if code:
    print('ERROR: ' + verb + ' failed')  # corpus_run counts lines starting with ERROR:
    print('ERROR: second problem')
sys.exit(code)
'''


def _write_exec(path, template):
    path = pathlib.Path(path)
    path.write_text(template.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def make_fake_gazelle(directory):
    return _write_exec(pathlib.Path(directory) / 'fake_gazelle', FAKE_GAZELLE)


def make_fake_bazel(directory):
    return _write_exec(pathlib.Path(directory) / 'fake_bazel', FAKE_BAZEL)


class EnvPatch:
    """Context manager that sets environment variables and restores them afterwards."""

    def __init__(self, **values):
        self.values, self.saved = values, {}

    def __enter__(self):
        for key, value in self.values.items():
            self.saved[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *exc):
        for key, old in self.saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
