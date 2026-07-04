from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_ralph_loop(
    args: list[str],
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run ralph-loop as a real subprocess (no mocks).

    Exercises subprocess spawning via PTY, real output reading, and
    promise detection end-to-end.
    """
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "ralph_loop", *args],
        input=input_data,
        capture_output=True,
        timeout=30,
        env=env,
    )


def test_readme_example_completes_on_promise() -> None:
    """E2E: minimal command that prints a promise and exits.

    Exercises:
    - Subprocess spawning via PTY (no mocks)
    - Promise detection on final output line
    - Clean exit code 0
    """
    result = _run_ralph_loop(
        [
            "-i",
            "1",
            "--",
            "sh",
            "-lc",
            "printf '<promise>DONE</promise>\\n'",
        ],
        input_data=None,
    )

    assert result.returncode == 0
    stdout = result.stdout.decode()
    assert "ralph-loop completed at iteration 1." in stdout


def test_iteration_limit_stops_loop() -> None:
    """E2E: loop stops at max-iterations when no promise is produced.

    Exercises:
    - Subprocess spawning via PTY (no mocks)
    - Sleep between iterations
    - Per-iteration timeout
    - Iteration limit reached (no promise)
    """
    result = _run_ralph_loop(
        [
            "-i",
            "3",
            "-t",
            "5",
            "-s",
            "0",
            "--",
            "sh",
            "-lc",
            "printf 'working...\\n'",
        ],
        input_data=None,
    )

    assert result.returncode == 0
    stdout = result.stdout.decode()
    assert "ralph-loop stopped after 3 iterations." in stdout


def test_piped_stdin_forwarded_to_wrapped_command() -> None:
    """E2E: echo test | ralph-loop -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\\n"'.

    Exercises:
    - Piped stdin (subprocess.run(input=...) makes isatty() False)
    - stdin_thread creation and _forward_stdin execution
    - cat reads stdin, printf writes promise
    - Promise detection on final output line
    - Clean exit code 0
    """
    result = _run_ralph_loop(
        [
            "-i",
            "1",
            "--",
            "sh",
            "-lc",
            "cat; printf '<promise>DONE</promise>\\n'",
        ],
        input_data=b"test\n",
    )

    assert result.returncode == 0
    stdout = result.stdout.decode()
    assert "test" in stdout
    assert "ralph-loop completed at iteration 1." in stdout
