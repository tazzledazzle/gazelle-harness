#!/usr/bin/env python3
"""Deterministic synthetic repositories for benchmarking Gazelle extensions (H7).

Usage: python3 tools/synth.py --lang python --packages 1000 --fanout 3 --out /tmp/synth-py-1000 [--seed 1] [--cycles 0.0]
Languages: python, java, kotlin, ts
"""
import argparse
import json
import pathlib
import random

# Gazelle -lang value for each synthetic language
LANG_FLAG = {'python': 'python', 'java': 'java', 'kotlin': 'kotlin', 'ts': 'js'}
# The file touched by a one-file-change benchmark, and its comment prefix
TOUCH = {'python': ('pkg_0/mod.py', '#'), 'java': ('java/p0/C0.java', '//'),
         'kotlin': ('kt/k0/K0.kt', '//'), 'ts': ('ts/pkg_0/index.ts', '//')}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_deps(n, fanout, cycles, seed):
    """deps[i] = the packages that package i imports."""
    rng = random.Random(seed)  # one generator for the whole repo keeps the output deterministic
    deps = []
    for i in range(n):
        lower = min(i, fanout)
        chosen = sorted(rng.sample(range(i), lower)) if lower else []
        if cycles and i + 1 < n and rng.random() < cycles:
            chosen.append(rng.randrange(i + 1, n))  # a back-edge creates a cycle
        deps.append(chosen)
    return deps


def gen_python(out, n, deps):
    for i in range(n):
        write(out / ('pkg_%d' % i) / '__init__.py', '')
        imports = ''.join('from pkg_%d.mod import f_%d' % (j, j) + chr(10) for j in deps[i])
        write(out / ('pkg_%d' % i) / 'mod.py', imports + 'def f_%d():' % i + chr(10) + '    return %d' % i + chr(10))
    write(out / 'BUILD.bazel', '# gazelle:python_extension enabled' + chr(10))
    manifest = ['manifest:', '  modules_mapping: {}', '  pip_repository:', '    name: pip', 'integrity: none']
    write(out / 'gazelle_python.yaml', chr(10).join(manifest) + chr(10))


def gen_java(out, n, deps):
    for i in range(n):
        imports = ''.join('import p%d.C%d;' % (j, j) + chr(10) for j in deps[i])
        body = 'package p%d;' % i + chr(10) + imports + 'public class C%d { public static int v() { return %d; } }' % (i, i) + chr(10)
        write(out / 'java' / ('p%d' % i) / ('C%d.java' % i), body)
    write(out / 'BUILD.bazel', '# gazelle:java_extension enabled' + chr(10))


def gen_kotlin(out, n, deps):
    for i in range(n):
        imports = ''.join('import k%d.f%d' % (j, j) + chr(10) for j in deps[i])
        body = 'package k%d' % i + chr(10) + imports + 'fun f%d(): Int = %d' % (i, i) + chr(10)
        write(out / 'kt' / ('k%d' % i) / ('K%d.kt' % i), body)
    write(out / 'BUILD.bazel', '# Kotlin directives go here once the extension exists' + chr(10))


def gen_ts(out, n, deps):
    for i in range(n):
        imports = ''.join('import { f_%d } from ../pkg_%d;' % (j, j) + chr(10) for j in deps[i])
        imports = imports.replace('../pkg_', chr(39) + '../pkg_').replace(';', chr(39) + ';')  # quote the module path
        body = imports + 'export function f_%d(): number { return %d; }' % (i, i) + chr(10)
        write(out / 'ts' / ('pkg_%d' % i) / 'index.ts', body)
    write(out / 'package.json', json.dumps({'name': 'synth', 'version': '1.0.0'}) + chr(10))
    write(out / 'tsconfig.json', json.dumps({'compilerOptions': {'strict': True}}) + chr(10))
    lock = ['lockfileVersion: ' + chr(39) + '9.0' + chr(39), 'importers:', '  .: {}', 'packages: {}', 'snapshots: {}']
    write(out / 'pnpm-lock.yaml', chr(10).join(lock) + chr(10))
    write(out / 'BUILD.bazel', '')


GENERATORS = {'python': gen_python, 'java': gen_java, 'kotlin': gen_kotlin, 'ts': gen_ts}


def generate(lang, out, n, fanout=3, seed=1, cycles=0.0):
    GENERATORS[lang](pathlib.Path(out), n, make_deps(n, fanout, cycles, seed))


def touch(root, lang, counter):
    """Change one source file (append a comment) so the next Gazelle run sees a modified input."""
    rel, prefix = TOUCH[lang]
    path = pathlib.Path(root) / rel
    path.write_text(path.read_text() + prefix + ' touched ' + str(counter) + chr(10))
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', required=True, choices=sorted(GENERATORS))
    parser.add_argument('--packages', type=int, required=True)
    parser.add_argument('--fanout', type=int, default=3)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--cycles', type=float, default=0.0)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    generate(args.lang, args.out, args.packages, args.fanout, args.seed, args.cycles)
    print('wrote ' + str(args.packages) + ' ' + args.lang + ' packages to ' + args.out)
