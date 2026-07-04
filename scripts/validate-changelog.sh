#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
CHANGELOG="$ROOT/CHANGELOG.md"

errors=0

if [[ ! -f "$CHANGELOG" ]]; then
	echo "FAIL: CHANGELOG.md not found at $CHANGELOG"
	exit 1
fi

# Check that the file starts with # Changelog heading
first_line=$(head -n1 "$CHANGELOG")
if [[ "$first_line" != "# Changelog" ]]; then
	echo "FAIL: CHANGELOG.md must start with '# Changelog'"
	errors=$((errors + 1))
fi

# Check that version entries follow ## [X.Y.Z] - YYYY-MM-DD format
if ! grep -qP '^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$' "$CHANGELOG"; then
	echo "FAIL: No valid version entry found (expected ## [X.Y.Z] - YYYY-MM-DD)"
	errors=$((errors + 1))
fi

# Extract the latest version entry (first ## [X.Y.Z] section)
latest_section=$(awk '/^## \[/{n++; if(n==1)} n==1' "$CHANGELOG")

# Check that the latest entry has why, model, and tags
if ! echo "$latest_section" | grep -q '\*\*why:\*\*'; then
	echo "FAIL: Latest version entry missing 'why' metadata"
	errors=$((errors + 1))
fi
if ! echo "$latest_section" | grep -q '\*\*model:\*\*'; then
	echo "FAIL: Latest version entry missing 'model' metadata"
	errors=$((errors + 1))
fi
if ! echo "$latest_section" | grep -q '\*\*tags:\*\*'; then
	echo "FAIL: Latest version entry missing 'tags' metadata"
	errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
	echo "FAIL: $errors validation error(s) found"
	exit 1
fi

echo "OK: CHANGELOG.md is valid"
exit 0
