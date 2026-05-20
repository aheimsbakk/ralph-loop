#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
	printf 'Usage: %s [patch|minor|major]\n' "$0" >&2
	exit 1
fi

kind="$1"

python3 - "$kind" <<'PY'
from __future__ import annotations

from pathlib import Path
import re
import sys


def bump(version: str, kind: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor += 1
        patch = 0
    elif kind == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise SystemExit(f"Unsupported bump kind: {kind}")
    return f"{major}.{minor}.{patch}"


def replace_in_file(path: Path, pattern: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not update version in {path}")
    path.write_text(updated, encoding="utf-8")


kind = sys.argv[1]
pyproject = Path("/work/pyproject.toml")
constants = Path("/work/src/ralph/constants.py")
lockfile = Path("/work/uv.lock")

match = re.search(r'^version = "(\d+\.\d+\.\d+)"$', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
if not match:
    raise SystemExit("Could not read version from pyproject.toml")

current = match.group(1)
new = bump(current, kind)

replace_in_file(pyproject, r'^version = "\d+\.\d+\.\d+"$', f'version = "{new}"')
replace_in_file(constants, r'^VERSION = "\d+\.\d+\.\d+"$', f'VERSION = "{new}"')
replace_in_file(lockfile, r'^(name = "ralph"\nversion = )"\d+\.\d+\.\d+"$', rf'\1"{new}"')

print(new)
PY
