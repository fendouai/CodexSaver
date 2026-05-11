# CodexSaver v2 Current-Window Install Test

Date: 2026-05-11

## Installation

- Editable CLI install: `python -m pip install -e .`
- Installed package: `codexsaver-0.2.0`
- CLI path: `/opt/anaconda3/bin/codexsaver`
- Top-level CLI help: `codexsaver --help` shows `install`, `doctor`, `auth`, `delegate`, and `work-packet`
- Imported package path: `/Users/f/GitHub/CodexSaver/codexsaver/__init__.py`
- Global Codex MCP launcher: `/Users/f/.codexsaver/codexsaver_mcp.py`
- Launcher source root: `/Users/f/GitHub/CodexSaver`
- Provider: `deepseek`
- Provider model: `deepseek-chat`
- Provider key source: local persisted config

## Doctor

`codexsaver doctor --workspace .` reported CodexSaver ready:

- global config exists and has `codexsaver`
- global launcher exists
- local provider config exists
- DeepSeek API key is configured from local config

## Important Current-Window Note

The already-open Codex MCP process did not hot-reload after installation. A direct
`codexsaver.delegate_work_packet` call in this window still used the old in-memory
server and fell back to Codex. The global launcher now points to v2, so a new Codex
window or MCP server reload will pick up the installed v2 server.

The benchmark below was run through the freshly installed editable CLI, which uses
the v2 source tree directly.

## Five-Task Benchmark

Method: Codex-only is a normalized counterfactual baseline with cost index `1.00`.
CodexSaver results are real bounded work-packet runs through the installed v2 CLI.
`worker` means DeepSeek produced a patch that passed sandbox verification.
`preflight` means the task was already satisfied and the allowlisted check passed
before any worker model call.

| Task | Kind | Mode | Status | Codex-only cost | CodexSaver cost | Savings | Effect | Latency |
|---|---|---|---|---:|---:|---:|---:|---:|
| Create v2 smoke doc | docs | worker | success | 1.00 | 0.55 | 45% | 1.0 | 2.36s |
| Add generated cost test | tests | worker | success | 1.00 | 0.55 | 45% | 1.0 | 9.30s |
| Add package version metadata | small_code | preflight | success | 1.00 | 0.00 | 100% | 1.0 | 0.03s |
| Document work-packet CLI | docs | worker | success | 1.00 | 0.55 | 45% | 1.0 | 3.86s |
| Create Chinese v2 note | zh_docs | worker | success | 1.00 | 0.55 | 45% | 1.0 | 2.68s |

## Summary

- Success rate: `5/5`
- Worker delegation: `4/5`
- Preflight already-satisfied: `1/5`
- Average latency: `3.65s`
- Worker-only average latency: `4.55s`
- Average normalized CodexSaver cost index: `0.44`
- Average estimated savings: `56%`
- Worker-only estimated savings: `45%`

## Verification

- Full unit test suite: `97 passed in 0.41s`
- Secret scan: no DeepSeek key or `sk-...` token found in git diff
- All benchmark patches were applied and checked in sandbox workspaces only
