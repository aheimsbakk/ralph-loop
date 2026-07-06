#!/usr/bin/env bash
# verify_codebase_sync.sh
# Validates that all physical file paths declared in CODEBASE.md exist.
# Run during the Synchronization Phase to detect orphaned references.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEBASE="$ROOT/CODEBASE.md"
errors=0

if [[ ! -f "$CODEBASE" ]]; then
	echo "FAIL: CODEBASE.md not found at $CODEBASE" >&2
	exit 1
fi

echo "Checking CODEBASE.md paths..."

# Extract all paths that look like file references (backtick-quoted paths)
# but skip table separator rows, headings, and markdown link targets.
#
# We match lines containing a backtick-quoted string that starts with
# src/, tests/, scripts/, pyproject.toml, uv.lock, README.md,
# CHANGELOG.md, or opencode.json.
paths=$(grep -oP '`((src|tests|scripts)/[^`]+|pyproject\.toml|uv\.lock|README\.md|CHANGELOG\.md|opencode\.json)`' "$CODEBASE" | sed 's/^`//;s/`$//')

while IFS= read -r path; do
	full_path="$ROOT/$path"
	if [[ ! -f "$full_path" && ! -d "$full_path" ]]; then
		echo "  MISSING: $path" >&2
		errors=$((errors + 1))
	else
		echo "  OK:      $path"
	fi
done <<<"$paths"

if [[ "$errors" -gt 0 ]]; then
	echo "FAIL: $errors path(s) referenced in CODEBASE.md do not exist." >&2
	exit 1
fi

echo "PASS: All CODEBASE.md paths exist."
