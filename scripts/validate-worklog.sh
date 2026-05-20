#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
	printf 'Usage: %s <worklog-path>\n' "$0" >&2
	exit 1
fi

worklog_path="$1"

python3 - "$worklog_path" <<'PY'
from __future__ import annotations

from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
lines = content.splitlines()

if len(lines) < 7 or lines[0] != "---":
    raise SystemExit("Worklog must start with YAML front matter")

try:
    closing_index = lines.index("---", 1)
except ValueError as error:
    raise SystemExit("Worklog front matter must end with ---") from error

front_matter = lines[1:closing_index]
expected_keys = ["when", "why", "what", "model", "tags"]
keys = [line.split(":", 1)[0] for line in front_matter if ":" in line]

if keys != expected_keys:
    raise SystemExit("Worklog front matter keys must be when, why, what, model, tags")

if len(front_matter) != len(expected_keys):
    raise SystemExit("Worklog front matter contains unexpected fields")

if closing_index == len(lines) - 1:
    raise SystemExit("Worklog body is required")
PY
