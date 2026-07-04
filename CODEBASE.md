# ralph-loop codebase

## Structure

### Package Root
- `pyproject.toml` — Package metadata, dependency definitions, and console script configuration.
- `uv.lock` — Locked dependency resolution from `uv`.
- `README.md` — Project documentation and usage guide.
- `CHANGELOG.md` — Version history and notable changes.
- `opencode.json` — Opencode tooling configuration.

### Source Code (`src/ralph_loop/`)
| Component | Physical Path | Description |
| :--- | :--- | :--- |
| Package Init | `src/ralph_loop/__init__.py` | Package entry, exports `VERSION`. |
| Interface Layer | `src/ralph_loop/cli.py` | Argument parsing and CLI entry orchestration. |
| Orchestration Layer | `src/ralph_loop/commands.py` | High-level iteration loop and option validation. |
| Runtime Layer | `src/ralph_loop/runtime.py` | Low-level execution, PTY management, and signal handling. |
| Data Layer | `src/ralph_loop/models.py` | Data structures for configuration and results. |
| Constants | `src/ralph_loop/constants.py` | Default values and version information. |
| Package Entry | `src/ralph_loop/__main__.py` | Module-level entry point. |

### Tests (`tests/`)
| Component | Physical Path | Description |
| :--- | :--- | :--- |
| CLI Tests | `tests/test_cli.py` | Verification of argument parsing and interface. |
| Orchestration Tests | `tests/test_commands.py` | Verification of loop and command logic. |
| Runtime Tests | `tests/test_runtime.py` | Verification of subprocess and signal handling. |
| Test Config | `tests/conftest.py` | Pytest fixtures and configuration. |

### Scripts (`scripts/`)
| Component | Physical Path | Description |
| :--- | :--- | :--- |
| Version Bump | `scripts/bump-version.sh` | Patches version across `pyproject.toml`, `constants.py`, and `uv.lock`. |
| Worklog Validator | `scripts/validate-worklog.sh` | Validates worklog YAML front-matter structure. |

## Specs
- **Language:** Python
- **Package Manager:** `uv`
- **Testing Framework:** `pytest`

## Entry Points
- `ralph-loop`: Defined in `pyproject.toml`, resolves to `ralph_loop.cli:main`.

## Language Rationale
- **Python**: Selected for its robust `subprocess` and `pty` libraries, enabling realistic terminal emulation and signal handling.
- **argparse**: Utilized for standardized CLI argument parsing.
- **pytest**: Employed for its extensive fixture support, essential for simulating complex runtime and signal scenarios.
