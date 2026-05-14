# CodexSaver

> Make Codex cheaper without making it dumber.

<p align="center">
  <a href="./README_zh.md"><strong>中文文档</strong></a>
</p>

![CodexSaver](./CodexSaver.png)

CodexSaver is an MCP tool that turns Codex into a cost-aware router.
It pushes low-risk development work to a cheaper worker LLM, keeps high-risk
judgment in Codex, and returns enough interaction detail that you can feel when
the tool is active.

- Lower-cost execution for tests, docs, search, and explanation work
- Codex stays responsible for architecture, security, protected domains, and final review
- Global-by-default Codex install, so every workspace can use the same MCP tool
- DeepSeek by default, with presets for OpenAI, Anthropic, Gemini, Qwen, Ollama, LM Studio, and more
- One-time local provider setup in `~/.codexsaver/config.json`
- Verified with tests, real DeepSeek calls, and end-to-end MCP launcher checks

---

## Why This Exists

Most coding sessions contain two very different kinds of work:

- expensive thinking
- cheap execution

Codex is excellent at the first one. It is overqualified for much of the second.

CodexSaver splits the flow on purpose:

- `Codex` handles reasoning, ambiguity, protected domains, and approval
- a configured worker provider handles low-risk throughput work

That gives you a practical pattern:

```text
Use the expensive model for judgment.
Use the cheaper model for volume.
Never confuse the two.
```

---

## What It Feels Like

When CodexSaver is active, tool responses are not silent blobs of JSON.
They include an `interaction` block that makes the routing decision visible:

```json
{
  "interaction": {
    "tool": "codexsaver.delegate_task",
    "mode": "delegated_execution",
    "headline": "CodexSaver delegated this task to the configured worker provider.",
    "route_label": "[CodexSaver] route=deepseek task_type=write_tests risk=low",
    "next_step": "Review the worker result and apply it only if the patch looks safe."
  }
}
```

Three states matter:

- `preview`: routing preview only, no external model call
- `delegated_execution`: delegated run completed
- `codex_takeover`: task stayed with Codex because risk was too high or the task was ambiguous

---

## V2: Bounded Work Packets

CodexSaver v2 adds a stricter delegation lane for work that should be safe but
still deserves proof. Instead of asking the worker to "just do the task", Codex
hands it a bounded work packet:

- exact goal
- allowed files or globs
- forbidden paths
- acceptance criteria
- allowlisted commands
- maximum iterations and diff size

The worker can propose patches, but CodexSaver applies them only inside a
temporary sandbox. The patch is accepted only when it stays within policy and
the allowlisted checks pass. If the task is already satisfied, v2 returns a
`preflight_satisfied=true` result without spending a worker model call.

CLI example:

```bash
codexsaver work-packet \
  "Create docs/v2-smoke.md with one sentence." \
  --files README.md \
  --allowed-file docs/v2-smoke.md \
  --acceptance "docs/v2-smoke.md exists in sandbox" \
  --allowed-command "python -c \"from pathlib import Path; assert Path('docs/v2-smoke.md').exists()\"" \
  --workspace .
```

MCP tool:

```text
codexsaver.delegate_work_packet
```

---

## Quick Start

### Recommended Global Install

```bash
git clone https://github.com/fendouai/CodexSaver
cd CodexSaver

python -m pip install -e .
codexsaver auth set --provider deepseek --api-key YOUR_API_KEY
codexsaver install
codexsaver doctor --workspace .
```

That is it. `codexsaver install` writes a global Codex MCP entry to
`~/.codex/config.toml` and points it at a stable launcher:
`~/.codexsaver/codexsaver_mcp.py`.

After that, every Codex workspace can call:

```text
codexsaver.delegate_task
```

Use `--project` only when you want a repository-local `.codex/config.toml`:

```bash
codexsaver install --project
```

### Provider Setup

DeepSeek is the default because it is inexpensive and exposes an OpenAI-compatible API.
Switching providers is just one flag:

```bash
codexsaver auth set --provider openai --api-key YOUR_API_KEY --model gpt-4o-mini
codexsaver auth set --provider anthropic --api-key YOUR_API_KEY --model claude-3-5-haiku-latest
codexsaver auth set --provider gemini --api-key YOUR_API_KEY --model gemini-2.0-flash
codexsaver auth set --provider qwen --api-key YOUR_API_KEY --model qwen-plus
```

For local models:

```bash
codexsaver auth set --provider ollama --model llama3.1
codexsaver auth set --provider lmstudio --model local-model
```

For any custom OpenAI-compatible endpoint:

```bash
codexsaver auth set \
  --provider custom \
  --api-key YOUR_API_KEY \
  --base-url https://example.com/v1/chat/completions \
  --model your-model
```

See built-in presets:

```bash
codexsaver auth providers
```

If you prefer a temporary one-shell-session setup instead of saving the key locally:

```bash
export CODEXSAVER_PROVIDER=deepseek
export CODEXSAVER_API_KEY=YOUR_API_KEY
codexsaver install
codexsaver doctor --workspace .
```

### One Message To Codex

If Codex is already open in this repository, you can just say:

```text
Save my worker provider API key for CodexSaver, run `codexsaver auth set --provider deepseek --api-key ...`, then run `codexsaver install` and `codexsaver doctor --workspace .`, and tell me whether it is ready.
```

For repo-local setup:

```text
Save my worker provider API key for CodexSaver, install CodexSaver only for this repo, run `codexsaver auth set --provider deepseek --api-key ...`, `codexsaver install --project`, then `codexsaver doctor --workspace .`, and summarize the result.
```

Ready means:

- `~/.codex/config.toml` contains the global `codexsaver` MCP server, or `.codex/config.toml` exists in the repo
- `~/.codexsaver/codexsaver_mcp.py` exists for global installs
- provider settings are available from env vars or `~/.codexsaver/config.json`
- `codexsaver doctor --workspace .` reports `CodexSaver is ready`

---

## 60-Second Demo

Global MCP config created by `codexsaver install`:

```toml
[mcp_servers.codexsaver]
command = "python"
args = ["/Users/you/.codexsaver/codexsaver_mcp.py"]
startup_timeout_sec = 10
tool_timeout_sec = 120
```

Then tell Codex:

```text
Use CodexSaver for safe low-risk tasks.
Add unit tests for user service.
```

Or call the CLI directly:

```bash
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
```

Dry run:

```bash
codexsaver delegate "add unit tests for user service" --files src/user/service.ts --workspace . --dry-run
```

Real run:

```bash
codexsaver delegate "add unit tests for user service" --files src/user/service.ts --workspace .
```

---

## Verified V2 Setup Flow

Measured on May 12, 2026 with the editable install, global launcher, and local-key workflow:

| Check | Command | Result |
|---|---|---|
| Editable install | `python -m pip install -e .` | installed `codexsaver-0.2.0` |
| Full test suite | `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` | `97 passed in 0.41s` |
| Global install | `codexsaver install --workspace .` | global config points at `~/.codexsaver/codexsaver_mcp.py` |
| Local provider persistence | `codexsaver auth set --provider deepseek --api-key ...` | saved to `~/.codexsaver/config.json` |
| Workspace doctor | `codexsaver doctor --workspace .` | `provider_api_key_source=local_config:deepseek`, workspace ready |
| Global launcher check | `python ~/.codexsaver/codexsaver_mcp.py` with MCP `initialize` | returned `serverInfo.version=0.2.0` |
| V2 MCP tool check | MCP `tools/list` | includes `delegate_work_packet` |
| V2 preflight check | MCP `tools/call delegate_work_packet` | returned `preflight_satisfied=true` |

This is the intended workflow:

1. Save the key once
2. Install the editable package and global launcher
3. Confirm readiness with `doctor`
4. Restart/reload any already-open MCP process if it was started before installation
5. Use real delegated calls without re-exporting API keys

If an already-open Codex window was using an older MCP process, stop or reload
that MCP server. The global launcher is the source of truth for v2 and returns
`serverInfo.version=0.2.0`.

---

## Provider Matrix

Built-in presets cover the common hosted and local routes:

| Provider | Style | Default model | API key |
|---|---|---|---|
| `deepseek` | OpenAI-compatible | `deepseek-chat` | required |
| `openai` | OpenAI | `gpt-4o-mini` | required |
| `anthropic` | native Messages API | `claude-3-5-haiku-latest` | required |
| `gemini` | OpenAI-compatible endpoint | `gemini-2.0-flash` | required |
| `qwen` | OpenAI-compatible endpoint | `qwen-plus` | required |
| `ollama` | local OpenAI-compatible endpoint | `llama3.1` | not required |
| `lmstudio` | local OpenAI-compatible endpoint | `local-model` | not required |

Run `codexsaver auth providers` for the complete list.

---

## Post-Setup Usage Ratio

After setup completed, I measured the actual routed tasks in this working session.
I only counted tasks that truly entered model routing, not local commands like `pytest`,
`git`, `install`, `doctor`, or README editing.

Result:

- `DeepSeek`: `7 / 8 = 87.5%`
- `Codex`: `1 / 8 = 12.5%`

Why not 100%?

One test-writing prompt originally included the phrase `production logic`.
That triggered the router's intentional high-risk keyword guard and returned the task to Codex.
This was not a failure. It was the protection logic working as designed.

If you only count the later standardized five-task benchmark with natural low-risk phrasing,
the delegation ratio was:

- `DeepSeek`: `5 / 5 = 100%`
- `Codex`: `0 / 5 = 0%`

Takeaway:

- In real usage, CodexSaver defaulted to DeepSeek for most low-risk work
- It still preserved a strict fallback path for risky wording and protected domains

---

## Five-Task A/B Benchmark

Latest v2 reports:

- [v2 restart confirmation, 2026-05-12](./docs/benchmarks/v2-restart-confirmation-2026-05-12.md)
- [v2 benchmark, 2026-05-12](./docs/benchmarks/v2-benchmark-2026-05-12.md)

The May 12 run was performed after stopping the older in-memory MCP process and
verifying the global launcher returned `serverInfo.version=0.2.0`.

Method:

- **A** = counterfactual `Codex-only` baseline with normalized cost index fixed at `1.00`
- **B** = `CodexSaver` mode with the live router and DeepSeek worker
- latency is wall-clock time for the real CodexSaver execution
- savings come from the current `CostEstimator`, so this is a reproducible routing benchmark, not invoice-grade billing data

V2 bounded work-packet summary:

- `5 / 5` tasks succeeded
- `4 / 5` used the DeepSeek worker path
- `1 / 5` used v2 preflight because the task was already satisfied
- average normalized cost index was `0.44`
- average estimated savings were `56%`

Summary:

- All 5 tasks were typical low-risk development chores: explanation, docs, tests, and README maintenance
- All 5 delegated successfully after using natural low-risk phrasing
- Average live latency was `6.18s`
- Average estimated savings were `48.4%`
- Average normalized cost moved from `1.00` to `0.52`
- Estimated relative reduction was `48.0%`

| Task | Type | Route | Latency | A: Codex-only Cost Index | B: CodexSaver Cost Index | Estimated Savings | Output Shape |
|---|---|---|---:|---:|---:|---:|---|
| Explain router logic | `explain` | `deepseek` | `2.13s` | `1.00` | `0.55` | `45%` | read-only summary |
| Document router module | `docs` | `deepseek` | `3.13s` | `1.00` | `0.55` | `45%` | 1-file patch |
| Add cost tests | `write_tests` | `deepseek` | `9.29s` | `1.00` | `0.55` | `45%` | test patch |
| Explain verifier flow | `explain` | `deepseek` | `2.30s` | `1.00` | `0.55` | `45%` | read-only summary |
| Update install docs | `docs` | `deepseek` | `14.06s` | `1.00` | `0.38` | `62%` | README patch |

![Five-task benchmark](./assets/ab-test-benchmark.svg)

Figure:
Gray bars are the `Codex-only` baseline fixed at `100`.
Green bars are the `CodexSaver` cost index for the same task.
Lower bars mean lower estimated Codex spend.

Interpretation:

- Read-only explain tasks were the fastest, cleanest wins
- Small docs edits delegated well and returned compact, reviewable patches
- Test generation had higher latency than explanation, but still stayed in the low-risk savings band
- Larger-context documentation work produced the biggest estimated savings because the Codex-only context cost would be higher

---

## Routing Rules

### Good Tasks To Delegate

- repo scanning and code search
- code explanation and summarization
- writing unit tests
- fixing lint or type errors
- documentation updates
- boilerplate generation
- small localized refactors

### Tasks Kept In Codex

- architecture decisions
- auth, security, payment, billing, or permissions logic
- database migrations
- deployment and production operations
- ambiguous product requests
- final review before applying changes

### Why Some Medium-Risk Tasks Still Delegate

CodexSaver does not just ask:

```text
Is this code work?
```

It asks:

```text
Is this code work cheap enough to delegate without losing judgment quality?
```

That creates a deliberate asymmetry:

- read-only understanding can be cheap
- writes in sensitive domains are expensive in risk even if the diff is small
- ambiguity defaults to Codex, not delegation

That is why `Explain auth code` may still delegate while `Refactor auth service` stays in Codex.

---

## How It Works

```text
User
  ↓
Codex
  ↓ MCP tool call
CodexSaver
  ├─ Router
  ├─ Context Packer
  ├─ Worker LLM Provider
  ├─ Verifier
  └─ Cost Estimator
  ↓
Codex review / apply / finalize
```

Core modules:

- `Router`: classify tasks and assign risk
- `ContextPacker`: bound file context before delegation
- `ProviderClient`: call the configured worker model
- `Verifier`: validate output shape, protected paths, and suggested commands
- `CostEstimator`: estimate relative savings bands
- `WorkPacketRuntime`: apply worker patches in a sandbox and run allowlisted checks

---

## Security And Persistence

- `codexsaver auth set --provider ... --api-key ...` saves provider settings to `~/.codexsaver/config.json`
- the config file is written with local-user-only permissions
- `doctor` shows whether the key comes from the environment or local config, and only prints a masked preview
- live calls use local config automatically if no env key is exported
- if verification fails, CodexSaver falls back to `needs_codex`

---

## Troubleshooting

### Windows TOML Unicode Escape Error

If Codex shows an error like this after installation:

```text
failed to read configuration layers ...\.codex\config.toml:21:14:
too few unicode value digits, expected unicode hexadecimal value
```

the Codex config contains an unescaped Windows path such as:

```toml
args = ["C:\Users\admin\.codexsaver\codexsaver_mcp.py"]
```

TOML treats `\U` as the start of a unicode escape. Fix it by upgrading to the
latest CodexSaver and reinstalling:

```bash
python -m pip install -e .
codexsaver install
codexsaver doctor --workspace .
```

Or repair the file manually by escaping backslashes:

```toml
args = ["C:\\Users\\admin\\.codexsaver\\codexsaver_mcp.py"]
```

Forward slashes also work on Windows:

```toml
args = ["C:/Users/admin/.codexsaver/codexsaver_mcp.py"]
```

---

## Commands

```bash
codexsaver auth providers
codexsaver auth set --provider deepseek --api-key YOUR_API_KEY
codexsaver install
codexsaver install --project
codexsaver doctor --workspace .
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
codexsaver work-packet "Create docs/example.md with one sentence." --files README.md --allowed-file docs/example.md --workspace .
```

---

## Roadmap

- [x] MCP server
- [x] rule-based routing
- [x] bounded context packing
- [x] DeepSeek default worker integration
- [x] multi-provider OpenAI-compatible worker support
- [x] local API key persistence
- [x] interaction-aware tool responses
- [x] end-to-end verification flow
- [x] v2 bounded work packets with sandboxed patch verification
- [x] v2 preflight for already-satisfied work packets
- [ ] cost-aware dynamic routing
- [ ] cost-aware provider selection

---

## If This Saves You Money

Star the repo.
