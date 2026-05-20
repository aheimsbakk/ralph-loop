---
when: 2026-05-20T22:01:50Z
why: Finalize Ralph support for passing OpenCode root options before the Ralph command.
what: Added pre-command OpenCode option passthrough, state persistence, tests, docs, and the v1.1.0 release update.
model: github-copilot/gpt-5.4
tags: [ralph, cli, opencode, testing, release]
---

This task taught `ralph` to forward supported OpenCode root options that appear before `start`, `status`, or `help`, while keeping `--help` and `--version` reserved for Ralph itself. It updated the CLI parser, state model, runtime command building, tests, and docs, and bumped the project to v1.1.0.
