"""Shared helpers for the harness tools (standard library only)."""
import json
import os
import pathlib
import subprocess
import time

# Repo root, found from this file so tools work from any current directory
ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)
    return None


def save_json(path, data):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)  # create folders on demand
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)  # sorted keys give stable diffs
        f.write(chr(10))  # trailing newline


def run(cmd, cwd=None, env=None, check=True, log=None):
    """Run a command, echo it, optionally write its output to a log file. Returns (exit_code, seconds)."""
    print('+ ' + ' '.join(str(c) for c in cmd) + (f'   (cwd={cwd})' if cwd else ''), flush=True)
    start = time.monotonic()  # monotonic clock is immune to wall-clock changes
    merged_env = {**os.environ, **(env or {})}
    if log:
        pathlib.Path(log).parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'w', encoding='utf-8') as log_file:
            proc = subprocess.run(cmd, cwd=cwd, env=merged_env, stdout=log_file, stderr=subprocess.STDOUT)
    else:
        proc = subprocess.run(cmd, cwd=cwd, env=merged_env)
    seconds = time.monotonic() - start
    if check and proc.returncode != 0:
        raise SystemExit(f'command failed ({proc.returncode}): {cmd[0]}')
    return proc.returncode, seconds


def gazelle_bin(cli_value=None):
    """Resolve the Gazelle binary from --gazelle or the GAZELLE_BIN variable."""
    value = cli_value or os.environ.get('GAZELLE_BIN')
    if not value or not os.path.exists(value):
        raise SystemExit('set GAZELLE_BIN or pass --gazelle (run: source scripts/env.sh)')
    return os.path.abspath(value)