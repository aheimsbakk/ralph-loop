from __future__ import annotations

from pathlib import Path
import argparse

import pytest

from ralph import cli
from ralph.constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
)


def test_main_without_args_prints_help(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main([], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Usage:" in captured.out
    assert "ralph start -a AGENT -m MODEL [options] <prompt>" in captured.out
    assert "CRITICAL - Ralph Loop Completion Promise" not in captured.out


def test_version_flag_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--version"])

    assert error.value.code == 0


def test_help_command_for_start(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["help", "start"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage: ralph start" in captured.out
    assert "CRITICAL - Ralph Loop Completion Promise" in captured.out
    assert "Hint: add the same completion promise to your prompt." in captured.out
    assert (
        "This is the standard contract Ralph injects before your task." in captured.out
    )
    assert "Standard injected prompt template:" in captured.out
    assert "<promise>{promise}</promise>" in captured.out


def test_help_command_for_root_includes_promise_guidance(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["help"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ralph help [start|status]" in captured.out
    assert "CRITICAL - Ralph Loop Completion Promise" in captured.out


def test_help_command_rejects_unknown_topic(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["help", "unknown"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "unknown help topic: unknown" in captured.err


def test_parser_error_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["--unknown"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error: unrecognized arguments: --unknown" in captured.err


def test_start_command_dispatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: dict[str, object] = {}

    def fake_start(args: argparse.Namespace, directory: Path) -> int:
        called["agent"] = args.agent
        called["opencode_args"] = args.opencode_args
        called["directory"] = directory
        return 7

    monkeypatch.setattr(cli, "start_command", fake_start)

    exit_code = cli.main(
        ["start", "-a", "vibe", "-m", "model", "Prompt"], directory=tmp_path
    )

    assert exit_code == 7
    assert called == {"agent": "vibe", "opencode_args": [], "directory": tmp_path}


def test_pre_command_opencode_options_are_forwarded_to_start_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: dict[str, object] = {}

    def fake_start(args: argparse.Namespace, directory: Path) -> int:
        called["opencode_args"] = args.opencode_args
        called["state_file"] = args.state_file
        called["model"] = args.model
        called["directory"] = directory
        return 0

    monkeypatch.setattr(cli, "start_command", fake_start)

    exit_code = cli.main(
        [
            "--print-logs",
            "-s",
            "session-123",
            "-m",
            "root/model",
            "start",
            "-a",
            "vibe",
            "-m",
            "task/model",
            "-s",
            "custom-state.md",
            "Prompt",
        ],
        directory=tmp_path,
    )

    assert exit_code == 0
    assert called == {
        "opencode_args": [
            "--print-logs",
            "-s",
            "session-123",
            "-m",
            "root/model",
        ],
        "state_file": "custom-state.md",
        "model": "task/model",
        "directory": tmp_path,
    }


def test_start_defaults_are_applied() -> None:
    parser, _ = cli.build_parser()
    args = parser.parse_args(["start", "-a", "vibe", "-m", "model", "Prompt"])

    assert args.max_iterations == DEFAULT_MAX_ITERATIONS
    assert args.completion_promise == DEFAULT_COMPLETION_PROMISE
    assert args.timeout == DEFAULT_TIMEOUT_SECONDS
    assert args.sleep == 0
    assert args.state_file == "ralph-loop.local.md"
    assert args.no_standard_prompt is False


def test_short_no_standard_prompt_option_is_supported() -> None:
    parser, _ = cli.build_parser()
    args = parser.parse_args(["start", "-a", "vibe", "-m", "model", "-P", "Prompt"])

    assert args.no_standard_prompt is True


def test_state_file_short_option_is_supported() -> None:
    parser, _ = cli.build_parser()
    args = parser.parse_args(
        ["start", "-a", "vibe", "-m", "model", "-s", "custom.md", "Prompt"]
    )

    assert args.state_file == "custom.md"


def test_cancel_is_no_longer_a_valid_command(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = cli.main(["cancel"], directory=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "invalid choice: 'cancel'" in captured.err
