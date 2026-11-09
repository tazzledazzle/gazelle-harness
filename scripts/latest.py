#!/usr/bin/env python3
"""Print the newest Bazel Central Registry version of each module named on the command line."""
import json
import sys
import urllib.request

# The registry keeps one metadata.json per module
BCR = 'https://bcr.bazel.build/modules/{}/metadata.json'

for name in sys.argv[1:]:
    # Network call; raises a clear HTTP error if the module name is wrong
    with urllib.request.urlopen(BCR.format(name)) as response:
        meta = json.load(response)
    versions = meta['versions']  # listed oldest to newest
    print(f'bazel_dep(name = "{name}", version = "{versions[-1]}")')
