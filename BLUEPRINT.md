# ralph-loop architecture

## Core

### System Goals
- Provide a thin, robust execution wrapper for any CLI-based command.
- Enable repeated execution of a command within a managed loop.
- Provide reliable termination mechanisms:
    - Completion promise detection (pattern matching on output).
    - Maximum iteration limit.
    - Bounded execution timeout per iteration.
    - Manual interruption via standard signals (e.g., SIGINT).

### Component Hierarchy
- **Interface Layer**: Orchestrates argument parsing and distinguishes between wrapper options and the wrapped command.
- **Orchestration Layer**: Manages the high-level loop lifecycle, option validation, and termination logic.
- **Runtime Layer**: Handles low-level execution environment, subprocess lifecycle, real-time output streaming, signal handling, and timer management.
- **Data Layer**: Defines the internal representation of configuration options and iteration outcomes.

### Data Flow
1. **Input Phase**: User provides configuration options and the target command via the command line.
2. **Validation Phase**: Orchestration layer validates the configuration and ensures the command is valid.
3. **Execution Loop**:
    - **Startup**: Runtime layer sets up the execution environment.
    - **Execution**: The wrapped command is executed.
    - **Streaming**: Output from the command is streamed to the user and captured for analysis.
    - **Analysis**: Output is sanitized (e.g., stripping terminal control codes) and checked against the completion promise.
    - **Iteration Control**: The loop evaluates exit codes, timeouts, iteration counts, and termination signals to decide whether to continue or exit.
4. **Completion Phase**: The loop terminates, and the final outcome is reported to the user.

### State Management
- The system maintains transient state for the current execution loop:
    - Current iteration count.
    - Elapsed time for the current iteration.
    - Captured output buffers.
    - Captured signal status.

## Contracts

### Entry Points
- `ralph-loop [options] -- <command> [args...]`
- The `--` separator is a mandatory contract to distinguish wrapper parameters from the target command's arguments.

### Payload Schemas
- **Options Schema**:
    - `max_iterations`: Non-negative integer.
    - `completion_promise`: String pattern for matching.
    - `timeout_seconds`: Positive integer.
    - `sleep_seconds`: Non-negative integer.
- **Iteration Outcome Schema**:
    - `exit_code`: Integer status from the wrapped process.
    - `output`: Captured text output from the process.

### Error Boundaries
- **Configuration Errors**: Validation failures for command options.
- **Execution Errors**: Failures within the wrapped command.
- **Interrupt Errors**: Graceful handling of termination signals.
- **Timeout Errors**: Termination of an iteration exceeding its allotted duration.

## Constraints
- Prefer Python standard library modules over third-party packages.

## External
- **Command Execution**: Interaction with external processes via standard input/output and signaling mechanisms.
- **Runtime Dependencies**: Python and `uv`.
