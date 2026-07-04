# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.0] - 2026-07-04

- **why:** Add sleep delay, session timeout, and end-to-end tests; refactor runtime into focused modules
- **model:** llama-cpp/qwen-3.6-think-coding
- **tags:** sleep, session-timeout, e2e-tests, refactoring

### Added

- `--sleep` / `-s` option to wait between successful iterations (`src/ralph_loop/cli.py`, `src/ralph_loop/commands.py`).
- `--session-timeout` option to limit the entire ralph-loop session duration (`src/ralph_loop/cli.py`, `src/ralph_loop/commands.py`).
- End-to-end test suite (`tests/test_e2e.py`) that spawns real subprocesses with PTY I/O and validates promise detection, iteration limits, and piped stdin forwarding.

### Changed

- Split `src/ralph_loop/runtime.py` into focused modules: `ProcessRunner` and `OutputReader` in `src/ralph_loop/process_runner.py`, `SignalHandler` in `src/ralph_loop/signal_handler.py`.
- Updated README with piped stdin usage example and session timeout guidance.

### Fixed

- `--session-timeout` no longer conflicts with `-s`/`--sleep` short option.

## [3.0.2] - 2026-05-21

### Fixed

- Updated example model name from `ollama/gemini4` to `ollama/gemma4` in README, CLI help text, and tests.

## [3.0.1] - 2026-05-21

### Fixed

- Aligned empty-command usage output with full help usage line.
- Reformatted help examples so wrapped commands stay readable.

## [3.0.0] - 2026-05-21

### Changed (Breaking)

- Renamed package from `ralph` to `ralph_loop`.
- Renamed installed command from `ralph` to `ralph-loop`.
- Updated all documentation, tests, and lockfile references.
- Fixed version bump script for the new package path.

## [2.0.0] - 2026-05-21

### Changed (Breaking)

- Removed stateful command flows (`start`, `status`).
- Replaced state-driven design with a thin loop wrapper: `ralph [options] -- <command>`.
- Removed shell entrypoint and state module.

### Removed

- Shell entrypoint script.
- State module and associated state-driven command flows.

## [1.1.0] - 2026-05-20

### Added

- Pre-command OpenCode option passthrough: supported OpenCode root options appearing before `start`, `status`, or `help`.
- Updated CLI parser, state model, and runtime command building to support passthrough.

## [1.0.2] - 2026-05-20

### Added

- Installable Python CLI package with `pyproject.toml` and `uv` lockfile.
- Runtime layer with PTY management, signal handling, and real-time output streaming.
- Test suite using `pytest`.
- Helper scripts for version bumping and worklog validation.

### Changed

- Replaced prior shell workflow with installable Python CLI.
- Updated loop behavior, streamed output, state handling, and completion detection.
- Refreshed README, architecture docs, and helper scripts.
