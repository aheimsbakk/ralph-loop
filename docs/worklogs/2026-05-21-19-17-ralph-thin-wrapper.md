---
when: 2026-05-21T19:17:31Z
why: Finalize the Ralph redesign as a thin loop wrapper for any CLI command.
what: Removed stateful command flows, updated docs and tests, and released Ralph v2.0.0.
model: github-copilot/gpt-5.4
tags: [ralph, cli, python, release, breaking-change]
---

This task simplified Ralph into a direct loop runner for any CLI command and replaced the old state-driven `start` and `status` flows with `ralph [options] -- <command>`. It also removed the shell entrypoint and state module, refreshed the docs and tests, and bumped the project to v2.0.0.
