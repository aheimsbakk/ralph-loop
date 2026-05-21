---
when: 2026-05-21T20:17:37Z
why: Fix the documented and help-text model name used in examples.
what: Updated examples to use ollama/gemma4 and bumped the release to v3.0.2.
model: github-copilot/gpt-5.4
tags: [docs, cli, release]
---

Updated `README.md`, `src/ralph_loop/cli.py`, and `tests/test_cli.py` so the example model name is `ollama/gemma4` everywhere. Bumped the package version to v3.0.2 in `pyproject.toml`, `src/ralph_loop/constants.py`, and `uv.lock`. Verified the project with `uv run pytest`.
