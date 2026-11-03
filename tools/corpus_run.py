#!/usr/bin/env python3
"""Regenerate BUILD files for a corpus repo with the polyglot Gazelle binary, then build and test.

Usage:
  python3 tools/corpus_run.py --id grpc-kotlin --gazelle "$GAZELLE_BIN"
  python3 tools/corpus_run.py --all --skip-tests
Output: .corpus/<id>/results.json and logs under .corpus/<id>/logs/
"""
import argparse
import pathlib
import re
import shutil
import sys

from common import ROOT, gazelle_bin, load_json, run, save_json
import corpus_fetch


def prepare_workspace(entry, base):
    """Copy the stripped tree to a fresh work directory and put the Gazelle directives in its root BUILD file."""
    work = base / 'work'
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(base / 'tree', work, symlinks=True)  # symlinks=True keeps links as links
    if entry.get('bazel_version'):
        (work / '.bazelversion').write_text(entry['bazel_version'] + chr(10))
    directives = entry.get('gazelle_directives', [])
    if directives:
        # Reuse an existing root BUILD file name so we never create a second, shadowing one
        root_build = next((work / n for n in ('BUILD.bazel', 'BUILD') if (work / n).exists()), work / 'BUILD.bazel')
        existing = root_build.read_text() if root_build.exists() else ''
        root_build.write_text(chr(10).join(directives) + chr(10) + existing)  # directives go first
    return work


def count_errors(log_path):
    """Count Bazel ERROR lines: a rough failure count for the report."""
    text = pathlib.Path(log_path).read_text(errors='replace')
    return len(re.findall('^ERROR:', text, flags=re.MULTILINE))


def run_one(entry, manifest, args):
    base = corpus_fetch.OUT_ROOT / entry['id']
    if not args.no_fetch:
        corpus_fetch.fetch(entry, manifest, args.use_upstream)
    work = prepare_workspace(entry, base)
    logs = base / 'logs'
    gazelle = gazelle_bin(args.gazelle)
    result = {'id': entry['id'], 'language': entry['language'], 'passed': False}

    # 1. Regenerate BUILD files; the whole point of the harness
    code, secs = run([gazelle, '-repo_root=' + str(work)] + entry.get('gazelle_args', []),
                     cwd=work, check=False, log=logs / 'gazelle.log')
    result['gazelle'] = {'exit': code, 'seconds': round(secs, 2)}
    ok = code == 0

    # 2. Build everything the manifest lists; --keep_going reports all failures, not just the first
    if ok and entry.get('targets'):
        code, secs = run([args.bazel, 'build', '--keep_going'] + entry['targets'],
                         cwd=work, check=False, log=logs / 'build.log')
        result['build'] = {'exit': code, 'seconds': round(secs, 2), 'errors': count_errors(logs / 'build.log')}
        ok = code == 0
        # 3. Test only when the build is green
        if ok and not args.skip_tests:
            code, secs = run([args.bazel, 'test', '--keep_going'] + entry['targets'],
                             cwd=work, check=False, log=logs / 'test.log')
            result['test'] = {'exit': code, 'seconds': round(secs, 2), 'errors': count_errors(logs / 'test.log')}
            ok = code == 0

    # 4. Optional: compare generated dependency edges with the originals (added in step 5)
    if ok and args.depdiff:
        import depdiff
        result['depdiff'] = depdiff.compare_corpus(entry['id'], args.bazel)

    result['passed'] = ok
    save_json(base / 'results.json', result)
    print(('PASS' if ok else 'FAIL') + '  ' + entry['id'] + '  (logs in ' + str(logs) + ')')
    return result


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id')
    group.add_argument('--all', action='store_true')
    parser.add_argument('--manifest', default=str(ROOT / 'corpus' / 'manifest.json'))
    parser.add_argument('--gazelle')
    parser.add_argument('--bazel', default='bazel')
    parser.add_argument('--skip-tests', action='store_true')
    parser.add_argument('--no-fetch', action='store_true')  # reuse the existing .corpus/<id>/tree
    parser.add_argument('--use-upstream', action='store_true')
    parser.add_argument('--depdiff', action='store_true')
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    chosen = [e for e in manifest['repos'] if args.all or e['id'] == args.id]
    if not chosen:
        raise SystemExit('no such repo id: ' + str(args.id))
    results = [run_one(entry, manifest, args) for entry in chosen]
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())