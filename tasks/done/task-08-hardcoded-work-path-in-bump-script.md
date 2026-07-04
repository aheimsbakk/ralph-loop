# task-08-hardcoded-work-path-in-bump-script

## Severity
Low

## Rule
IV.23 (Dependencies)

## Summary
Replace hardcoded `/work` path with project-root-relative resolution.

## Problem
`scripts/bump-version.sh` uses `Path("/work/pyproject.toml")` and similar
hardcoded paths. This breaks if the repository is cloned to a different
directory or used in a different environment.

## Evidence
`scripts/bump-version.sh`: `pyproject = Path("/work/pyproject.toml")`

## Fix
1. Resolve the project root relative to the script's location:
   `ROOT = Path(__file__).resolve().parent.parent` (for the Python portion).
2. In the bash wrapper, use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
   and `ROOT="$(dirname "$SCRIPT_DIR")"`.
3. Pass `ROOT` as an environment variable or argument to the Python script.

## Files
- `scripts/bump-version.sh`

## Tests
- Run the script from a non-/work directory and verify it still updates versions.
