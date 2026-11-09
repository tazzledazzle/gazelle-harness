#!/usr/bin/env python3
"""Validate corpus/manifest.json so an unfinished manifest fails fast instead of failing a nightly job.

Usage: python3 tools/validate_manifest.py [--manifest corpus/manifest.json] [--allow-unpinned]
--allow-unpinned skips the commit and fork_owner checks, for use while you are still pinning (corpus_fetch.py --pin).
"""
import argparse
import re
import sys

from common import ROOT, load_json

REQUIRED_KEYS = ('id', 'language', 'upstream', 'fork_repo', 'commit', 'strip_dirs',
                 'gazelle_args', 'gazelle_directives', 'targets', 'bazel_version', 'notes')
LANGUAGES = {'java', 'kotlin', 'python', 'ts'}
COMMIT = re.compile('^[0-9a-f]{40}$')  # a full SHA-1; abbreviated ids can become ambiguous in a big repo
PLACEHOLDER = re.compile('REPLACE|TODO|FIXME')  # tokens that mark a value nobody has filled in yet


def walk_strings(value, path):
    """Yield (path, text) for every string inside a nested JSON value."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from walk_strings(item, path + '[' + str(i) + ']')
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, path + '.' + key)


def validate(manifest, allow_unpinned=False):
    """Return a list of human-readable problems; an empty list means the manifest is usable."""
    errors = []
    if not allow_unpinned and PLACEHOLDER.search(str(manifest.get('fork_owner', ''))):
        errors.append('fork_owner is still a placeholder: ' + str(manifest.get('fork_owner')))
    if not manifest.get('fork_owner'):
        errors.append('fork_owner is empty')
    repos = manifest.get('repos') or []
    if not repos:
        errors.append('manifest has no repos')
    ids = [r.get('id') for r in repos]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append('duplicate id: ' + str(dup))
    pinned = {}  # upstream URL -> {commit: [ids]}; entries sharing an upstream must share a commit
    for r in repos:
        rid = str(r.get('id'))
        for key in REQUIRED_KEYS:
            if key not in r:
                errors.append(rid + ': missing key ' + key)
        if r.get('language') not in LANGUAGES:
            errors.append(rid + ': language must be one of ' + ', '.join(sorted(LANGUAGES)))
        if not str(r.get('upstream', '')).startswith('https://'):
            errors.append(rid + ': upstream must be an https URL')
        if not r.get('strip_dirs'):
            errors.append(rid + ': strip_dirs is empty, so no BUILD files would be stripped')
        if not r.get('targets'):
            errors.append(rid + ': targets is empty, so nothing would be built')
        for path, text in walk_strings(r, rid):
            if PLACEHOLDER.search(text):
                errors.append(path + ': placeholder text left in the manifest (' + text[:40] + ')')
        commit = r.get('commit', '')
        if not allow_unpinned and not COMMIT.match(commit):
            errors.append(rid + ': commit must be a full 40-character SHA, got ' + repr(commit))
        pinned.setdefault(r.get('upstream'), {}).setdefault(commit, []).append(rid)
    for upstream, by_commit in pinned.items():
        if len(by_commit) > 1:
            detail = '; '.join(c[:10] + ' for ' + ', '.join(i) for c, i in sorted(by_commit.items()))
            errors.append('entries sharing ' + str(upstream) + ' are pinned to different commits: ' + detail)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default=str(ROOT / 'corpus' / 'manifest.json'))
    parser.add_argument('--allow-unpinned', action='store_true')
    args = parser.parse_args()
    errors = validate(load_json(args.manifest), args.allow_unpinned)
    for error in errors:
        print('FAIL  ' + error)
    print('manifest ok' if not errors else str(len(errors)) + ' problem(s) in ' + args.manifest)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
