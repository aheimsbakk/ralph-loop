# task-09-no-pyright-strict-mode

## Severity
Low

## Rule
— (Quality)

## Summary
Enable pyright `strict` type-checking mode.

## Problem
`pyproject.toml` configures pyright but does not enable `strict` mode.
With 7 source files, enabling strict mode would catch latent type issues
such as implicit `Any`, missing return annotations, and untyped imports.

## Evidence
`pyproject.toml`: `[tool.pyright]` section has no `typeCheckingMode`.

## Fix
1. Add `typeCheckingMode = "strict"` to `[tool.pyright]` in `pyproject.toml`.
2. Fix any type errors that arise (likely missing annotations, `Any` casts,
   or untyped third-party imports).
3. If some files cannot be strict-compliant, add `# pyright: ignore` with a
   reason on a per-file basis.

## Files
- `pyproject.toml`
- `src/ralph_loop/*.py` (as needed)

## Tests
- Run `pyright` and verify zero errors in strict mode.
