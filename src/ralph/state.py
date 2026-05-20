from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .constants import STATE_FILE
from .models import RalphState


FRONT_MATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
PROMISE_PATTERN = re.compile(r"<promise>([\s\S]*?)</promise>")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ScalarValue = str | int | bool | None | list[str]


def state_path(directory: Path, state_file: str = STATE_FILE) -> Path:
    path = Path(state_file)
    if path.is_absolute():
        return path
    return directory / path


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def strip_terminal_control_sequences(value: str) -> str:
    without_ansi = ANSI_ESCAPE_PATTERN.sub("", value)
    return without_ansi.replace("\r", "")


def promise_detected(text: str, expected: str | None) -> bool:
    if not expected:
        return False

    cleaned_text = strip_terminal_control_sequences(text)
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if not lines:
        return False

    match = PROMISE_PATTERN.fullmatch(lines[-1])
    if not match:
        return False

    return normalize_whitespace(match.group(1)) == normalize_whitespace(expected)


def _escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_scalar(value: str) -> ScalarValue:
    stripped = value.strip()
    if stripped == "null":
        return None
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return parsed
        return stripped
    if stripped.startswith('"') and stripped.endswith('"'):
        inner = stripped[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    return stripped


def load_state(directory: Path, state_file: str = STATE_FILE) -> RalphState | None:
    path = state_path(directory, state_file)
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(content)
    if not match:
        return None

    front_matter, body = match.groups()
    values: dict[str, ScalarValue] = {}

    for line in front_matter.splitlines():
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue
        values[key.strip()] = _parse_scalar(raw_value)

    return RalphState(
        active=_bool_value(values, "active", False),
        status=_string_value(values, "status"),
        iteration=_int_value(values, "iteration", 0),
        max_iterations=_int_value(values, "max_iterations", 0),
        completion_promise=_string_value(values, "completion_promise"),
        timeout_seconds=_int_value(values, "timeout_seconds", 3600),
        sleep_seconds=_int_value(values, "sleep_seconds", 0),
        inject_standard_prompt=_bool_value(values, "inject_standard_prompt", True),
        started_at=_string_value(values, "started_at"),
        updated_at=_string_value(values, "updated_at"),
        agent=_string_value(values, "agent"),
        model=_string_value(values, "model"),
        opencode_args=_string_tuple_value(values, "opencode_args"),
        pid=_int_or_none(values, "pid"),
        last_exit_code=_int_or_none(values, "last_exit_code"),
        prompt=body.lstrip("\n").rstrip("\n"),
    )


def save_state(
    directory: Path, state: RalphState, state_file: str = STATE_FILE
) -> None:
    path = state_path(directory, state_file)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    lines = [
        "---",
        f"active: {'true' if state.active else 'false'}",
        f"status: {_yaml_scalar(state.status)}",
        f"iteration: {state.iteration}",
        f"max_iterations: {state.max_iterations}",
        f"completion_promise: {_yaml_scalar(state.completion_promise)}",
        f"timeout_seconds: {state.timeout_seconds}",
        f"sleep_seconds: {state.sleep_seconds}",
        f"inject_standard_prompt: {_yaml_scalar(state.inject_standard_prompt)}",
        f"started_at: {_yaml_scalar(state.started_at)}",
        f"updated_at: {_yaml_scalar(state.updated_at)}",
        f"agent: {_yaml_scalar(state.agent)}",
        f"model: {_yaml_scalar(state.model)}",
        f"opencode_args: {_yaml_scalar(state.opencode_args)}",
        f"pid: {_yaml_scalar(state.pid)}",
        f"last_exit_code: {_yaml_scalar(state.last_exit_code)}",
        "---",
        "",
        state.prompt,
        "",
    ]
    temp_path.write_text("\n".join(lines), encoding="utf-8")
    temp_path.replace(path)


def _yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value))
    return f'"{_escape_yaml(str(value))}"'


def _string_value(values: dict[str, ScalarValue], key: str) -> str | None:
    value = values.get(key)
    return value if isinstance(value, str) else None


def _string_tuple_value(values: dict[str, ScalarValue], key: str) -> tuple[str, ...]:
    value = values.get(key)
    return tuple(value) if isinstance(value, list) else ()


def _int_value(values: dict[str, ScalarValue], key: str, default: int) -> int:
    value = values.get(key)
    return value if isinstance(value, int) else default


def _int_or_none(values: dict[str, ScalarValue], key: str) -> int | None:
    value = values.get(key)
    return value if isinstance(value, int) else None


def _bool_value(values: dict[str, ScalarValue], key: str, default: bool) -> bool:
    value = values.get(key)
    return value if isinstance(value, bool) else default
