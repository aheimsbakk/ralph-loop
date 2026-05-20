from __future__ import annotations

from pathlib import Path

from ralph.models import RalphState
from ralph.state import (
    load_state,
    normalize_whitespace,
    promise_detected,
    strip_terminal_control_sequences,
    save_state,
    state_path,
)


def test_save_and_load_state_round_trip(tmp_path: Path) -> None:
    state = RalphState(
        active=True,
        status="running",
        iteration=3,
        max_iterations=9,
        completion_promise='DONE "NOW"',
        timeout_seconds=45,
        sleep_seconds=2,
        inject_standard_prompt=False,
        started_at="2026-05-20T00:00:00Z",
        updated_at="2026-05-20T00:01:00Z",
        agent="vibe",
        model="ollama/gemini4",
        opencode_args=("--print-logs", "--session", "session-123"),
        pid=321,
        last_exit_code=0,
        prompt="Build docs",
    )

    save_state(tmp_path, state)
    loaded = load_state(tmp_path)

    assert loaded == state


def test_load_state_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert load_state(tmp_path) is None


def test_state_path_accepts_custom_relative_file(tmp_path: Path) -> None:
    assert state_path(tmp_path, "custom.md") == tmp_path / "custom.md"


def test_load_state_returns_none_for_invalid_front_matter(tmp_path: Path) -> None:
    (tmp_path / "ralph-loop.local.md").write_text("invalid", encoding="utf-8")

    assert load_state(tmp_path) is None


def test_promise_detected_normalizes_whitespace() -> None:
    output = "before\n<promise>DONE   NOW</promise>\n"

    assert promise_detected(output, "DONE NOW") is True


def test_promise_detected_handles_missing_expected_value() -> None:
    assert promise_detected("<promise>DONE</promise>", None) is False


def test_promise_detected_ignores_non_final_promise_line() -> None:
    output = "I will only output <promise>DONE</promise> when truly complete.\nStill working.\n"

    assert promise_detected(output, "DONE") is False


def test_promise_detected_accepts_final_non_empty_promise_line() -> None:
    output = "Still working.\n<promise>DONE</promise>\n\n"

    assert promise_detected(output, "DONE") is True


def test_promise_detected_ignores_terminal_control_sequences() -> None:
    output = "\x1b[2K\r<promise>hello said</promise>\x1b[0m\r\n"

    assert promise_detected(output, "hello said") is True


def test_strip_terminal_control_sequences_removes_ansi_and_carriage_returns() -> None:
    assert (
        strip_terminal_control_sequences("\x1b[2K\r<promise>DONE</promise>\x1b[0m\r")
        == "<promise>DONE</promise>"
    )


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace(" one\n\t two   three ") == "one two three"
