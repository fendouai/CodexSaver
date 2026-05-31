# CodexSaver

> Make Codex cheaper without making it dumber.

<p align="center">
  <a href="./README_zh.md"><strong>中文文档</strong></a>
</p>

![CodexSaver](./CodexSaver.png)

CodexSaver is an MCP tool that turns Codex into a cost-aware router.
Its current product story is intentionally narrow:

- win first on readonly specialists such as explanation, search, and review
- win second on bounded, verifiable patch work
- keep risky judgment and final review in Codex

- Lower-cost execution for tests, docs, search, and explanation work
- Codex stays responsible for architecture, security, protected domains, and final review
- Global-by-default Codex install, so every workspace can use the same MCP tool
- Pi Agent is the default v3 worker, with automatic discovery for other local Agent Card workers
- DeepSeek and other LLM providers remain available for legacy v1/v2 provider-backed delegation
- One-time local provider setup in `~/.codexsaver/config.json`
- Optional worker-output compression for shorter, review-friendly delegated results
- Verified with tests, Pi Agent routing smoke checks, historical DeepSeek calls, and end-to-end MCP launcher checks

---

## At A Glance

CodexSaver is not trying to replace Codex.
It is trying to **shrink expensive Codex work without losing engineering judgment**.

Current repo-local evidence:

| Dimension | What CodexSaver already proves |
|---|---|
| Cost | v2 benchmark reached `45%` to `100%` estimated savings on 5 bounded tasks |
| Speed | v2 5-task run completed successful tasks in `0.03s` to `14.95s`; v3 readonly swarm succeeded in `6.45s` |
| Quality | v2 bounded work packets passed verifier gates; v3 readonly swarm produced `10` findings with `0.75` quality score |
| Safety | protected paths, allowlisted commands, sandboxed patch apply, and Codex fallback are built in |

The current shape is simple:

- v2 is the mature lane for single bounded tasks
- v3 is the orchestration lane
- the clearest proven v3 advantage today is **readonly specialist orchestration**
- the next proven v3 advantage is **higher patch success through verified repair**

---

## Where CodexSaver Wins

CodexSaver is strongest when work is low-risk, easy to verify, and expensive for Codex but cheap for a smaller worker.

In practice, the strongest lanes are:

- code explanation
- repository scanning
- performance hinting
- docstrings and README maintenance
- bounded test generation
- small bounded refactors with explicit file scope

It is not strongest at:

- auth, security, payment, permissions
- destructive migrations
- ambiguous architecture decisions
- multi-file behavioral changes with weak verification
- anything that still needs Codex-level judgment at every step

The current product thesis is:

```text
CodexSaver wins first on readonly specialist orchestration.
CodexSaver wins second on bounded, verifiable patch work.
Codex remains the judge for everything risky or unclear.
```

That ordering matches both the implementation and the benchmark data.

---

## Why It Works

CodexSaver improves cost, speed, and quality through a small but strict split of responsibilities:

### 1. Lower Cost

Codex is used for judgment, not repetitive throughput work. Cheap workers handle:

- explanation
- docs
- tests
- small bounded implementation tasks

This keeps the expensive model away from routine throughput.

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

CodexSaver does not trust worker output blindly. It improves quality with hard boundaries:

- router decides whether the task is safe enough
- work packet limits the write scope
- sandbox applies patch in isolation
- verifier checks changed files, diff size, commands, and failures
- Codex still reviews the result

That is why CodexSaver can be cheaper **without** becoming a "YOLO auto-edit bot."

---

## Core Split

Most coding sessions mix expensive thinking with cheap execution.
CodexSaver splits them on purpose:

- `Codex` handles reasoning, ambiguity, protected domains, and approval
- a configured worker provider handles low-risk throughput work

The practical rule is:

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
    "route_label": "[CodexSaver] route=pi_agent task_type=write_tests risk=low",
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
- v3.4 adds action-level risk policy, partial handoff, and worker participation metrics
- v3.5 adds verified patch orchestration with strict patch output, lint, and node-level repair
- v3.6 adds Agent Card discovery, weighted worker routing, and task lifecycle metadata
- v3 is implemented as a CodexSaver-owned orchestration layer, not as a fragile Codex-native subagent config dependency

Primary references:

- [v3 spec](./docs/SPEC_v3.md)
- [v3 task list](./docs/V3_TASKS.md)
- [v3 benchmark, 2026-05-14](./docs/benchmarks/v3-benchmark-2026-05-14.md)
- [v3 project benchmark, 2026-05-15](./docs/benchmarks/v3-project-benchmark-2026-05-15.md)
- [v3.4 SWE-style benchmark, 2026-05-17](./docs/benchmarks/v34-swe-benchmark-2026-05-17.md)
- [v3.6 Agent routing smoke test, 2026-05-19](./docs/benchmarks/v36-agent-routing-smoke-2026-05-19.md)
- [v3.6 Pi Agent real-task benchmark, 2026-05-19](./docs/benchmarks/v36-pi-agent-benchmark-2026-05-19.md)
- [v3.6 patch success benchmark, 2026-05-31](./docs/benchmarks/v36-patch-success-benchmark-2026-05-31.md)

Current benchmark status:

- `readonly_swarm`: now live-tested through Pi Agent + DeepSeek V4 Flash on 5 repo tasks
- `impl + tests`: exercised, but still conservative and may return `needs_codex`
- `impl + docs + explain`: completed successfully in the 2026-05-14 fixture run

This means v3 is already real and testable, but still in an honest early stage rather than a full replacement for every v2 workflow.

### V3.4: Action-Level Delegation And Handoff

v3.4 changes the router from "does this task contain a risky word?" to "which actions inside this task are safe to delegate?"

Examples:

- `schema + readonly inspection` can go to Pi Agent
- `schema + dry-run validation plan` can go to Pi Agent
- `schema + execute migration` stays in Codex
- `database + destructive rebuild` is split into safe prep nodes plus blocked Codex-only actions

This is what lets Pi Agent and other local workers carry more of the work without crossing the line into writes, migrations, secrets, auth, payment, or deployment execution. CodexSaver now returns a `handoff` object with delegated work done, blocked actions, and Codex next actions, so Codex can continue smoothly instead of starting over.

### V3.5: Verified Patch Orchestration

v3.5 makes patch-producing nodes stricter before CodexSaver tries to aggregate them.
Patch workers must now return a structured result:

- `intent`
- `changed_files`
- `patch`
- `verification_plan`
- `rollback_notes`

Before aggregation, CodexSaver runs patch lint:

- rejects empty patches
- checks that `changed_files` exactly matches the diff
- rejects duplicate file writes in the same batch
- verifies the patch stays inside allowed files
- applies the patch in a sandbox before materializing it

If a patch node fails, v3.5 retries that node with repair context instead of throwing away the whole graph immediately.
Repairable patch-lint failures now get the same node-local treatment: CodexSaver can repair a bad `changed_files` declaration, a missing `verification_plan`, or a weak `test_writer` verification plan before returning `needs_codex`.
`test_writer` also has stronger hard checks now:

- it must change at least one `tests/test_*.py` file for Python
- `verification_plan` must mention the exact generated test file in a `pytest` command
- `rollback_notes` must explain how to delete or revert the generated test file

Worker metrics now include `repair_count`, so benchmark reports can show whether patch success came from first-pass output or bounded repair.

### V3.6: Agent Card Registry And Weighted Routing

v3.6 moves CodexSaver from hardcoded DeepSeek worker assumptions toward Pi Agent-first dynamic worker discovery.
Workers can be described by `.agent-card.json` files under `.pi-agents/`, `.pi/agents/`,
or `~/.codexsaver/agents`:

```json
{
  "id": "pi-agent-default",
  "name": "Pi Agent Worker",
  "type": "pi",
  "status": "online",
  "capabilities": ["code_generation", "testing", "docs"],
  "languages": ["python", "javascript"],
  "endpoint": "local:pi-side-agents",
  "command": ["pi", "--provider", "deepseek", "--model", "deepseek-v4-flash", "--mode", "json", "--no-session", "-p"],
  "worktree_path": ".pi-worktrees/pi-agent",
  "permissions_config": ".pi/permissions.json",
  "cost_weight": 0.1
}
```

CodexSaver scores discovered workers instead of using a brittle `if/else` tree:

| Dimension | Weight |
|---|---:|
| Capability match | `0.40` |
| Historical success | `0.25` |
| Cost weight | `0.20` |
| Current load | `0.10` |
| Context fit | `0.05` |

The orchestration dry-run now includes the discovered Agent Cards and the selected Pi/local worker for every node. Real execution results include `selected_worker` and an A2A-compatible task lifecycle:

```text
submitted -> running -> completed
                  -> failed
                  -> timed_out
```

CLI:

```bash
codexsaver agents list --workspace .
codexsaver agents init --workspace .
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py --dry-run
```

v3.6 smoke test results:

- Targeted tests: `22 passed in 0.20s`
- Builtin Agent Card discovery: passed
- Dry-run selected `pi-agent-default` for `explainer` and `perf_reviewer`
- Weighted route score for both readonly Python nodes: `0.98`
- Live execution no longer silently falls back to DeepSeek; if the Pi command is unavailable, v3.6 returns `needs_codex`

### Core Selling Point: Readonly Specialist Orchestration Works

The most important v3 claim is no longer theoretical. In the project benchmark run on
2026-05-15, the readonly specialist lane succeeded on the current CodexSaver codebase:

- Task: `Explain installer flow and review performance`
- Route: `pi_agent`
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

### v3.4: SWE-Style Participation Benchmark

Reference:

- [v3.4 SWE-style benchmark, 2026-05-17](./docs/benchmarks/v34-swe-benchmark-2026-05-17.md)

Headline result on six local SWE-style tasks:

- average worker participation reached `55.7%`
- `5 / 6` tasks reached at least `50%` worker participation
- `2 / 6` tasks completed successfully end-to-end
- fallback tasks still preserved partial worker output through handoff

### v3.6: Pi Agent Real-Task Benchmark

Reference:

- [v3.6 Pi Agent real-task benchmark, 2026-05-19](./docs/benchmarks/v36-pi-agent-benchmark-2026-05-19.md)

Headline result on five live readonly orchestration tasks:

- `5 / 5` tasks succeeded
- average latency was `18.63s`
- measured Pi/DeepSeek worker cost was `$0.00968315`
- same token volume under the documented Codex baseline was estimated at `$0.47955374`
- estimated savings reached `98%`
- average quality score was `1.0`
- worker participation reached `100%`

Summary table:

| Lane | Best current use | Status |
|---|---|---|
| v2 | single bounded patch tasks | mature |
| v3 readonly | explain + scan + perf hint specialists | established |
| v3.4 action-level orchestration | safe prep, dry-run planning, partial handoff | established enough to exceed 50% worker participation |
| v3 patch orchestration | docs/tests/impl mixed graphs | promising but still maturing |

If you are evaluating CodexSaver today, the right mental model is:

- use v2 when you want reliable bounded implementation
- use v3 when you want Codex to cheaply orchestrate readonly specialists
- use v3.4 when a larger SWE task contains safe prep work plus blocked high-risk actions
- treat multi-patch v3 graphs as an advancing frontier, not solved magic

---

## Quick Start

### Dependencies

CodexSaver keeps the core small:

| Dependency | Required for | Notes |
|---|---|---|
| Python `3.10+` | CodexSaver CLI and MCP server | runtime code uses the Python standard library |
| Node.js + npm | installing Pi Agent | needed for v3.6 live worker orchestration |
| Pi Agent CLI | default v3.6 worker | installed from `@earendil-works/pi-coding-agent` |
| DeepSeek API key | Pi Agent worker model + v1/v2 provider lane | saved once, reused locally |

### Recommended Global Install

```bash
git clone https://github.com/fendouai/CodexSaver
cd CodexSaver

python -m pip install -e .
npm install -g @earendil-works/pi-coding-agent
codexsaver auth set --provider deepseek --api-key YOUR_DEEPSEEK_API_KEY
codexsaver install
codexsaver doctor --workspace .
codexsaver agents list --workspace .
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py --workspace .
```

That is the default v3.6 path. `codexsaver auth set --provider deepseek ...`
saves the key for both CodexSaver and Pi Agent:

- `~/.codexsaver/config.json`
- `~/.pi/agent/auth.json`

Both files are written with `0600` permissions. `codexsaver install` writes a
global Codex MCP entry to `~/.codex/config.toml` and points it at a stable
launcher: `~/.codexsaver/codexsaver_mcp.py`.

After that, every Codex workspace can call:

```text
codexsaver.delegate_task
codexsaver.orchestrate_task
codexsaver.run_specialist
```

Use `--project` only when you want a repository-local `.codex/config.toml`:

```bash
codexsaver install --project
```

### Provider Setup

v3.6 uses Pi Agent through Agent Cards. The DeepSeek key saved above is used by
the default Pi Agent command:

```bash
pi --provider deepseek --model deepseek-v4-flash --mode json --no-session -p "Say ok"
```

Provider setup is also useful for the legacy v1/v2 `delegate_task` and
`delegate_work_packet` lanes. Switching that provider-backed lane is one flag:

```bash
codexsaver auth set --provider openai --api-key YOUR_API_KEY --model gpt-4o-mini
codexsaver auth set --provider anthropic --api-key YOUR_API_KEY --model claude-3-5-haiku-latest
codexsaver auth set --provider gemini --api-key YOUR_API_KEY --model gemini-2.0-flash
codexsaver auth set --provider qwen --api-key YOUR_API_KEY --model qwen-plus
codexsaver auth set --provider opencode-go --api-key YOUR_API_KEY --model deepseek-v4-flash
```

OpenCode Go uses `https://opencode.ai/zen/go/v1/chat/completions` and is useful
when you want CodexSaver's worker lane to run through its low-cost DeepSeek V4
Flash or Pro models. The default preset uses `deepseek-v4-flash`; switch to
`deepseek-v4-pro` if you want the stronger Go model.

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
Clone CodexSaver if needed, install it with `python -m pip install -e .`, install Pi Agent with `npm install -g @earendil-works/pi-coding-agent`, save my DeepSeek key with `codexsaver auth set --provider deepseek --api-key ...`, then run `codexsaver install`, `codexsaver doctor --workspace .`, and `codexsaver agents list --workspace .`.
```

For repo-local setup:

```text
Clone CodexSaver if needed, install it and Pi Agent, save my DeepSeek key with `codexsaver auth set --provider deepseek --api-key ...`, install CodexSaver only for this repo with `codexsaver install --project`, then run `codexsaver doctor --workspace .` and `codexsaver agents list --workspace .`.
```

Ready means:

- `~/.codex/config.toml` contains the global `codexsaver` MCP server, or `.codex/config.toml` exists in the repo
- `~/.codexsaver/codexsaver_mcp.py` exists for global installs
- provider settings are available from env vars or `~/.codexsaver/config.json`
- Pi Agent is installed and visible as `pi`
- the DeepSeek key is available to Pi in `~/.pi/agent/auth.json`
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

## Verified V3.6 Setup Flow

Measured on May 20, 2026 with the editable install, Pi Agent, global launcher,
and local DeepSeek key workflow:

| Check | Command | Result |
|---|---|---|
| Clone source | `git clone https://github.com/fendouai/CodexSaver` | source checkout first |
| Editable install | `python -m pip install -e .` | installs `codexsaver` CLI |
| Pi Agent install | `npm install -g @earendil-works/pi-coding-agent` | installs `pi` CLI |
| Key persistence | `codexsaver auth set --provider deepseek --api-key ...` | saves `~/.codexsaver/config.json` and `~/.pi/agent/auth.json` |
| Global MCP install | `codexsaver install` | global config points at `~/.codexsaver/codexsaver_mcp.py` |
| Workspace doctor | `codexsaver doctor --workspace .` | reports CodexSaver, Pi Agent, and key readiness |
| Agent discovery | `codexsaver agents list --workspace .` | discovers `pi-agent-default` |
| Live v3.6 smoke | `codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py --workspace .` | `route=pi_agent`, `status=success` |
| Full test suite | `python -m pytest -q -p no:cacheprovider` | current suite passes |

This is the intended workflow:

1. Clone the repository.
2. Install CodexSaver and Pi Agent.
3. Save the DeepSeek key once.
4. Install the global MCP launcher.
5. Confirm readiness with `doctor` and `agents list`.
6. Use v3.6 Pi Agent orchestration without re-exporting API keys.

If an already-open Codex window was using an older MCP process, stop or reload
that MCP server. The global launcher is the source of truth and returns
`serverInfo.version=0.3.6`.

---

## Provider Matrix

Built-in presets cover the common hosted and local routes:

| Provider | Style | Default model | API key |
|---|---|---|---|
| `deepseek` | OpenAI-compatible | `deepseek-chat` | required |
| `openai` | OpenAI | `gpt-4o-mini` | required |
| `anthropic` | native Messages API | `claude-3-5-haiku-latest` | required |
| `opencode-go` | OpenAI-compatible | `deepseek-v4-flash` | required |
| `gemini` | OpenAI-compatible endpoint | `gemini-2.0-flash` | required |
| `qwen` | OpenAI-compatible endpoint | `qwen-plus` | required |
| `ollama` | local OpenAI-compatible endpoint | `llama3.1` | not required |
| `lmstudio` | local OpenAI-compatible endpoint | `local-model` | not required |

Run `codexsaver auth providers` for the complete list.

---

## V3.6 Five-Task Benchmark

Latest v3.6 reports:

- [v3.6 Pi Agent benchmark, 2026-05-19](./docs/benchmarks/v36-pi-agent-benchmark-2026-05-19.md)
- [v3.6 agent routing smoke, 2026-05-19](./docs/benchmarks/v36-agent-routing-smoke-2026-05-19.md)
- [v3.6 patch success benchmark, 2026-05-31](./docs/benchmarks/v36-patch-success-benchmark-2026-05-31.md)

Method:

- **A** = counterfactual `Codex-only` baseline using the same task text and file scope
- **B** = `CodexSaver` v3.6 orchestration through Agent Registry and the default Pi Agent
- latency is wall-clock time for the real CodexSaver execution
- savings are estimated from measured worker usage plus the current cost estimator, so this is a reproducible engineering benchmark, not invoice-grade billing data

Summary:

- `5 / 5` real low-risk tasks succeeded
- `5 / 5` routed through `pi_agent`
- average worker participation was `100%`
- average latency was `18.63s`
- measured worker cost was `$0.00968315`
- estimated Codex-only baseline cost was `$0.47955374`
- estimated savings were about `98%`
- quality score was `1.0` across the benchmark because all returned outputs were structurally valid and reviewable

| Task | Type | Route | Worker | Latency | Quality | Output Shape |
|---|---|---|---|---:|---:|---|
| Explain config loader | read-only explain | `pi_agent` | `pi-agent-default` | measured live | `1.0` | concise summary |
| Review performance hot spots | read-only review | `pi_agent` | `pi-agent-default` | measured live | `1.0` | prioritized notes |
| Summarize installer flow | read-only docs | `pi_agent` | `pi-agent-default` | measured live | `1.0` | implementation summary |
| Explain registry routing | read-only explain | `pi_agent` | `pi-agent-default` | measured live | `1.0` | architecture summary |
| Review orchestrator risks | read-only review | `pi_agent` | `pi-agent-default` | measured live | `1.0` | risk notes |

![Five-task benchmark](./assets/ab-test-benchmark.svg)

Figure:
Gray bars are the `Codex-only` baseline fixed at `100`.
Green bars are the `CodexSaver` cost index for the same task.
Lower bars mean lower estimated Codex spend.

Interpretation:

- Read-only specialist orchestration is the cleanest v3.6 advantage: high worker participation, easy review, and almost no merge risk
- Pi Agent gives CodexSaver a real local worker without hardcoding one model provider into the router
- Codex still owns final judgment, but CodexSaver can now do the cheap scanning, explaining, and review drafting work first
- Historical v2 DeepSeek-provider benchmarks remain in `docs/benchmarks/` for comparison, but v3.6's default path is Pi Agent-first orchestration

## V3.6 Patch Success Benchmark

Latest report:

- [v3.6 patch success benchmark, 2026-05-31](./docs/benchmarks/v36-patch-success-benchmark-2026-05-31.md)

Method:

- deterministic orchestration benchmark, not a live model-quality benchmark
- each scenario replays fixed worker outputs against the current orchestrator
- the same scenarios are compared against a simulated pre-fix v3.5 baseline
- this isolates the value of lint repair, stricter `test_writer` validation, and bounded patch recovery

Summary:

- `baseline_write_success_rate`: `0.4`
- `current_write_success_rate`: `0.8`
- `baseline_verified_outcome_rate`: `0.2`
- `current_verified_outcome_rate`: `1.0`
- `verified_outcome_gain`: `+4 / 5` scenarios
- `average_repair_count`: `0.8`

Interpretation:

- the biggest practical gain comes from repairing fixable patch-lint failures instead of returning to Codex immediately
- `test_writer` is stricter in a useful way: weak pytest plans no longer count as acceptable output unless they mention the generated test file exactly
- duplicate writes still return `needs_codex`; that remained blocked on purpose and counts as preserved safety, not reduced capability

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
  ├─ Agent Registry
  ├─ Agent Router
  ├─ Router
  ├─ Context Packer
  ├─ Pi Agent Worker
  ├─ Verifier
  └─ Cost Estimator
  ↓
Codex review / apply / finalize
```

Core modules:

- `AgentRegistry`: discover Pi Agent and local worker Agent Cards
- `AgentRouter`: score workers by capability, cost, load, and fit
- `Router`: classify tasks and assign risk
- `ContextPacker`: bound file context before delegation
- `PiAgentClient`: call the default local Pi Agent worker
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
- [x] Pi Agent default v3 worker integration
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
