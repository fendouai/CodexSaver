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
- Optional worker-output compression for shorter, review-friendly delegated results
- Verified with tests, real DeepSeek calls, and end-to-end MCP launcher checks

---

## At A Glance

CodexSaver is not trying to replace Codex.
It is trying to **shrink the amount of expensive Codex work** without losing engineering judgment.

Current repo-local evidence:

| Dimension | What CodexSaver already proves |
|---|---|
| Cost | v2 benchmark reached `45%` to `100%` estimated savings on 5 bounded tasks |
| Speed | v2 5-task run completed successful tasks in `0.03s` to `14.95s`; v3 readonly swarm succeeded in `6.45s` |
| Quality | v2 bounded work packets passed verifier gates; v3 readonly swarm produced `10` findings with `0.75` quality score |
| Safety | protected paths, allowlisted commands, sandboxed patch apply, and Codex fallback are built in |

The important nuance:

- v2 is the mature lane for single bounded tasks
- v3 is the emerging lane for orchestrated specialists
- the first clearly established v3 win is **readonly specialist orchestration**

---

## Where CodexSaver Wins

CodexSaver is strongest in work that is:

- low-risk
- repetitive
- easy to verify
- parallelizable
- expensive for Codex but cheap for a smaller worker

In practice, that means CodexSaver is best at:

- code explanation
- repository scanning
- performance hinting
- docstrings and README maintenance
- bounded test generation
- small bounded refactors with explicit file scope

CodexSaver is not strongest at:

- auth, security, payment, permissions
- destructive migrations
- ambiguous architecture decisions
- multi-file behavioral changes with weak verification
- anything that still needs Codex-level judgment at every step

The current product thesis is simple:

```text
CodexSaver wins first on readonly specialist orchestration.
CodexSaver wins second on bounded, verifiable patch work.
Codex remains the judge for everything risky or unclear.
```

That ordering matters. It matches the current implementation and the current benchmark data.

---

## Why It Works

CodexSaver improves cost, speed, and quality through a very specific technical split:

### 1. Lower Cost

Codex is used for judgment, not repetitive throughput work.
Cheap worker models handle:

- explanation
- docs
- tests
- small bounded implementation tasks

That means the expensive model is no longer paying for every routine step.

### 2. Higher Speed

When the task is decomposable, CodexSaver can parallelize specialist work:

- one specialist explains
- one specialist reviews performance
- one specialist writes docs or tests

For these tasks, total latency starts to look like:

```text
max(single specialist runtime) + orchestration overhead
```

instead of:

```text
sum(all subtask runtimes)
```

### 3. Better Quality

CodexSaver does not trust worker output blindly.
It improves output quality with hard boundaries:

- router decides whether the task is safe enough
- work packet limits the write scope
- sandbox applies patch in isolation
- verifier checks changed files, diff size, commands, and failures
- Codex still reviews the result

That is why CodexSaver can be cheaper **without** becoming a "YOLO auto-edit bot."

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

When worker-output compression is enabled, the same `interaction` block includes
the active compression level so Codex can see why delegated replies are terser.

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

## V3: Orchestrated Specialists

CodexSaver v3 extends v2 from a single bounded worker into a small orchestrated specialist system.
The important shift is architectural:

- Codex still owns judgment and final review
- CodexSaver plans a work graph
- readonly specialists can run in parallel
- bounded patch specialists reuse the v2 sandbox + verifier path
- patch aggregation is conservative and falls back to Codex on overlap

Current v3 status in this repo:

- `explainer` and `perf_reviewer` can execute as a real `readonly_swarm`
- mixed graphs can execute bounded patch nodes through the v2 work-packet runtime
- overlapping `changed_files` across the same patch batch return `needs_codex`
- v3 is implemented as a CodexSaver-owned orchestration layer, not as a fragile Codex-native subagent config dependency

Primary references:

- [v3 spec](./docs/SPEC_v3.md)
- [v3 task list](./docs/V3_TASKS.md)
- [v3 benchmark, 2026-05-14](./docs/benchmarks/v3-benchmark-2026-05-14.md)
- [v3 project benchmark, 2026-05-15](./docs/benchmarks/v3-project-benchmark-2026-05-15.md)

Current benchmark status:

- `readonly_swarm`: exercised, but still saw real-provider fallback in the 2026-05-14 fixture run
- `impl + tests`: exercised, but still conservative and may return `needs_codex`
- `impl + docs + explain`: completed successfully in the 2026-05-14 fixture run

This means v3 is already real and testable, but still in an honest early stage rather than a full replacement for every v2 workflow.

### Core Selling Point: Readonly Specialist Orchestration Works

The most important v3 claim is no longer theoretical. In the project benchmark run on
2026-05-15, the readonly specialist lane succeeded on the current CodexSaver codebase:

- Task: `Explain installer flow and review performance`
- Route: `deepseek`
- Status: `success`
- Savings: `52%`
- Latency: `6.45s`
- Quality score: `0.75`
- Readonly findings: `10`

That is the current v3 core value:

- Codex delegates explanation and performance analysis cheaply
- specialists run in parallel
- no patch is required
- verification remains strict
- Codex still reviews the result

This is the first domain where v3 is clearly better than "just ask Codex to do everything."

### What The 5-Task Project Benchmark Says

The project benchmark ran 5 typical tasks against a temporary copy of the current repository:

- 2 / 5 tasks succeeded in v3
- both successful tasks were in CodexSaver's strongest current domains
- one success was pure readonly orchestration
- one success was a docs + explain mixed flow
- 3 / 5 patch-heavy tasks conservatively returned `needs_codex`

Interpretation:

- readonly specialist orchestration is already a real product advantage
- bounded patch orchestration is promising but still less mature than the readonly lane
- test-writer aggregation and patch verification are the main remaining bottlenecks

If you want the shortest honest description of v3 today, it is this:

```text
Readonly orchestration is established.
Single bounded patches are usable.
Complex patch orchestration is still maturing.
```

CLI examples:

```bash
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py
codexsaver orchestrate "Implement login and add tests" --files src/user_auth.py --dry-run
codexsaver specialist explainer "Explain this module" --files codexsaver/config.py
```

Optional project guidance install:

```bash
# low-intrusion: only add a managed CodexSaver block to AGENTS.md
codexsaver superpower install --profile basic --workspace .

# more invasive: also add .codex/hooks.json, a prompt hook script, and local codex_hooks enablement
codexsaver superpower install --profile full --workspace .
```

Profile guidance:

- `basic`: safest default, project-local AGENTS guidance only
- `full`: AGENTS guidance + optional hook scaffolding + local `.codex/config.toml` feature flag

The goal is to bias Codex toward CodexSaver for low-risk work without silently mutating global config.

---

## Benchmarks

CodexSaver now has two benchmark stories, and both matter:

### v2: Mature Single-Task Lane

Reference:

- [v2 benchmark, 2026-05-12](./docs/benchmarks/v2-benchmark-2026-05-12.md)

Headline result:

- `5 / 5` successful bounded tasks
- successful tasks landed at `45%` estimated savings
- one already-satisfied task returned `preflight` with `100%` savings and `0.03s` latency

This is the current strongest production-ready lane:

- bounded docs
- bounded tests
- small single-target implementation

### v3: Real Project-Oriented Orchestration

Reference:

- [v3 project benchmark, 2026-05-15](./docs/benchmarks/v3-project-benchmark-2026-05-15.md)

Headline result on the current CodexSaver repository:

- `2 / 5` tasks succeeded
- both successful tasks were in CodexSaver's strongest current domains
- the cleanest success was `readonly_swarm`
- patch-heavy orchestration still falls back conservatively

Summary table:

| Lane | Best current use | Status |
|---|---|---|
| v2 | single bounded patch tasks | mature |
| v3 readonly | explain + scan + perf hint specialists | established |
| v3 patch orchestration | docs/tests/impl mixed graphs | promising but still maturing |

If you are evaluating CodexSaver today, the right mental model is:

- use v2 when you want reliable bounded implementation
- use v3 when you want Codex to cheaply orchestrate readonly specialists
- treat multi-patch v3 graphs as an advancing frontier, not solved magic

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

### Worker Output Compression

Compression only affects delegated worker calls. It does not change Codex's own
final answer. It is useful when you want cheaper workers to return shorter,
more reviewable summaries, findings, or patch notes.

```bash
codexsaver compression show
codexsaver compression set --enabled true --level full
codexsaver compression set --enabled false
```

Levels:

- `lite`: concise, keeps technical terms and exact details
- `full`: compressed fragments, no greetings or filler, preserves code and errors
- `ultra`: telegraphic, essential facts and identifiers only
- `wenyan`: terse classical Chinese style for Chinese workflows

Default is disabled. The setting is persisted in `~/.codexsaver/config.json`.

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
- compression settings are available from `~/.codexsaver/config.json`
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
| Compression config | `codexsaver compression set --enabled true --level full` | saved to `~/.codexsaver/config.json` |
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
- `codexsaver compression set ...` saves optional worker-output compression in the same local config
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
codexsaver compression show
codexsaver compression set --enabled true --level full
codexsaver install
codexsaver install --project
codexsaver doctor --workspace .
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
codexsaver work-packet "Create docs/example.md with one sentence." --files README.md --allowed-file docs/example.md --workspace .
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py
codexsaver specialist explainer "Explain this module" --files codexsaver/config.py
```

---

## Roadmap

- [x] MCP server
- [x] rule-based routing
- [x] bounded context packing
- [x] DeepSeek default worker integration
- [x] multi-provider OpenAI-compatible worker support
- [x] local API key persistence
- [x] worker output compression toggles and provider prompt injection
- [x] interaction-aware tool responses
- [x] end-to-end verification flow
- [x] v2 bounded work packets with sandboxed patch verification
- [x] v2 preflight for already-satisfied work packets
- [x] v3 readonly specialist orchestration
- [x] v3 bounded patch nodes via the v2 sandbox runtime
- [x] v3 conflict fallback on overlapping patch outputs
- [ ] v3 node-level ownership enforcement
- [ ] v3 durable ledger and adaptive routing

---

## If This Saves You Money

Star the repo.
