from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ralph import cli
from ralph.constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
)
from ralph.models import RalphOptions


def test_main_without_args_prints_help(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main([], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Usage:" in captured.out
    assert "ralph [options] -- <command> [args...]" in captured.out
    assert "<promise>DONE</promise>" not in captured.out


def test_version_flag_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--version"])

    assert error.value.code == 0


def test_help_flag_includes_promise_guidance_and_examples(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"], directory=tmp_path)

    captured = capsys.readouterr()

    assert error.value.code == 0
    assert "usage: ralph [options] -- <command> [args...]" in captured.out
    assert "Ralph only detects the promise." in captured.out
    assert "--timeout applies to each iteration" in captured.out
    assert "--max-iterations 0 means run without an iteration limit." in captured.out
    assert "ralph -c DONE -- opencode run" in captured.out


def test_parser_error_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["--unknown"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error: unrecognized arguments: --unknown" in captured.err


def test_missing_separator_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["-i", "2"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error: missing command separator '--'" in captured.err


def test_missing_wrapped_command_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["-i", "2", "--"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error: missing wrapped command after '--'" in captured.err


def test_run_command_dispatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: dict[str, object] = {}

    def fake_run(options: RalphOptions, directory: Path) -> int:
        called["wrapped_command"] = options.wrapped_command
        called["completion_promise"] = options.completion_promise
        called["directory"] = directory
        return 7

    monkeypatch.setattr(cli, "run_command", fake_run)

    exit_code = cli.main(
        ["-c", "COMPLETE", "--", "opencode", "run", "Prompt"],
        directory=tmp_path,
    )

    assert exit_code == 7
    assert called == {
        "wrapped_command": ("opencode", "run", "Prompt"),
        "completion_promise": "COMPLETE",
        "directory": tmp_path,
    }


def test_start_defaults_are_applied() -> None:
    parser = cli.build_parser()
    args = parser.parse_args([])

    assert args.max_iterations == DEFAULT_MAX_ITERATIONS
    assert args.completion_promise == DEFAULT_COMPLETION_PROMISE
    assert args.timeout == DEFAULT_TIMEOUT_SECONDS
    assert args.sleep == 0


def test_short_sleep_option_is_supported() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["-s", "5"])

    assert args.sleep == 5


def test_long_sleep_option_is_supported() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["--sleep", "5"])

    assert args.sleep == 5
