#!/usr/bin/env python3
'''Fetch a corpus repo from your fork at a pinned commit, strip BUILD files, keep the originals.

Usage:
  python3 tools/corpus_fetch.py --id dagger --use-upstream --pin   # first time, before forks exist
  python3 tools/corpus_fetch.py --id dagger                        # later: fork URL + pinned commit
  python3 tools/corpus_fetch.py --all
Output under .corpus/<id>/: tree/ (stripped), original_builds/ (removed files), META.json
'''
import argparse
import fnmatch
import pathlib
import shutil
import subprocess

from common import ROOT, load_json, save_json

MANIFEST = ROOT / 'corpus' / 'manifest.json'
OUT_ROOT = ROOT / '.corpus'
CACHE_ROOT = pathlib.Path.home() / '.cache' / 'gazelle-harness' / 'git'
# Only these are stripped: MODULE.bazel, WORKSPACE and .bzl files are kept for the nested build
BUILD_NAMES = {'BUILD', 'BUILD.bazel'}


def git(args, cwd=None, check=True):
    proc = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit('git ' + ' '.join(args) + ' failed: ' + proc.stderr.strip())
    return proc


def repo_url(manifest, entry, use_upstream):
    if use_upstream:
        return entry['upstream']
    if manifest['fork_owner'].startswith('REPLACE'):
        raise SystemExit('set fork_owner in corpus/manifest.json, or pass --use-upstream')
    return 'https://github.com/' + manifest['fork_owner'] + '/' + entry['fork_repo'] + '.git'


def ensure_checkout(url, commit, cache_dir):
    '''Make cache_dir a git repo that contains the commit.'''
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not (cache_dir / '.git').exists():
        git(['init', '-q'], cwd=cache_dir)
    git(['remote', 'remove', 'origin'], cwd=cache_dir, check=False)  # allow URL changes between runs
    git(['remote', 'add', 'origin', url], cwd=cache_dir)
    if git(['cat-file', '-e', commit + '^{commit}'], cwd=cache_dir, check=False).returncode == 0:
        return  # already cached
    shallow = git(['fetch', '-q', '--depth', '1', 'origin', commit], cwd=cache_dir, check=False)
    if shallow.returncode != 0:  # some servers refuse a bare commit id; fall back to a full fetch
        git(['fetch', '-q', 'origin'], cwd=cache_dir)
    git(['cat-file', '-e', commit + '^{commit}'], cwd=cache_dir)


def export_tree(cache_dir, commit, dest):
    '''Write the files of the commit (no .git directory) into dest.'''
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.Popen(['git', 'archive', commit], cwd=cache_dir, stdout=subprocess.PIPE)
    untar = subprocess.run(['tar', '-x', '-C', str(dest)], stdin=archive.stdout)
    archive.stdout.close()
    if archive.wait() != 0 or untar.returncode != 0:
        raise SystemExit('git archive | tar failed')


def strip_builds(tree, originals, strip_dirs):
    '''Move matching BUILD files from tree to originals; return how many were moved.'''
    moved = 0
    for path in sorted(tree.rglob('*')):  # sorted() makes a list first, so moving files is safe
        if path.name not in BUILD_NAMES or not path.is_file():
            continue
        rel = path.relative_to(tree)
        directory = rel.parent.as_posix()  # '.' for the repository root
        if any(fnmatch.fnmatch(directory, pattern) for pattern in strip_dirs):
            target = originals / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved += 1
    return moved


def pin(manifest, entry, url):
    '''Resolve the default-branch head of the URL and store it in the manifest.'''
    out = git(['ls-remote', url, 'HEAD']).stdout.split()
    if not out:
        raise SystemExit('could not resolve HEAD of ' + url)
    entry['commit'] = out[0]
    save_json(MANIFEST, manifest)
    print('pinned ' + entry['id'] + ' to ' + entry['commit'])


def fetch(entry, manifest, use_upstream=False, do_pin=False):
    url = repo_url(manifest, entry, use_upstream)
    if do_pin:
        pin(manifest, entry, url)
    if not entry.get('commit'):
        raise SystemExit(entry['id'] + ' has no pinned commit; run once with --pin')
    base = OUT_ROOT / entry['id']
    cache = CACHE_ROOT / entry['id']
    ensure_checkout(url, entry['commit'], cache)
    originals = base / 'original_builds'
    if originals.exists():
        shutil.rmtree(originals)
    export_tree(cache, entry['commit'], base / 'tree')
    moved = strip_builds(base / 'tree', originals, entry['strip_dirs'])
    if moved == 0:
        print('WARNING: ' + entry['id'] + ': no BUILD files matched strip_dirs ' + str(entry['strip_dirs']))
    save_json(base / 'META.json', {'id': entry['id'], 'commit': entry['commit'], 'url': url, 'stripped': moved})
    print('fetched ' + entry['id'] + ' @ ' + entry['commit'][:10] + ', stripped ' + str(moved) + ' BUILD files')
    return base


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id')
    group.add_argument('--all', action='store_true')
    parser.add_argument('--use-upstream', action='store_true')  # fetch from the public repo instead of your fork
    parser.add_argument('--pin', action='store_true')  # record the current head commit in the manifest
    args = parser.parse_args()
    manifest = load_json(MANIFEST)
    chosen = [e for e in manifest['repos'] if args.all or e['id'] == args.id]
    if not chosen:
        raise SystemExit('no such repo id: ' + str(args.id))
    for entry in chosen:
        fetch(entry, manifest, args.use_upstream, args.pin)


if __name__ == '__main__':
    main()