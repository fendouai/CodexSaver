# CodexSaver v3 — Spec Document

> **Codex orchestrates. Specialists execute. Verifier gates. Codex decides.**

---

## 1. Concept & Positioning

CodexSaver v3 is a **multi-worker orchestration layer** built inside the CodexSaver MCP server.
It does not assume Codex itself exposes a stable native subagent registry with per-agent provider routing.
Instead, Codex remains the primary reasoning surface, and CodexSaver becomes the execution fabric for cheap,
specialized, parallel workers.

**Core idea**

- Codex owns planning, ambiguity handling, risk judgment, and final review.
- CodexSaver owns decomposition, specialist dispatch, sandboxed execution, verification, and aggregation.
- Pi Agent is the default local worker; other local Agent Card workers can join the pool.

**Slogan**

_Pi Agent does the local work. Codex keeps the judgment._

---

## 2. Why v3 Exists

v1 solved one problem:

```text
delegate a single low-risk task to a cheaper model
```

v2 solved a harder problem:

```text
let the worker propose a bounded patch, verify it in a sandbox, and repair within limits
```

v3 solves the next bottleneck:

```text
one worker is still too serial
```

Many real coding tasks are mixtures of independent subproblems:

- implement a small feature
- generate tests
- add docs
- explain risks
- suggest performance improvements

These tasks should not all consume the same expensive model turn.
v3 treats them as a coordinated fan-out/fan-in system.

---

## 3. Non-Goals

v3 is intentionally not:

- a replacement for Codex
- a full autonomous merge bot
- a blind parallel patch generator without verification
- dependent on unstable or undocumented Codex native subagent config keys
- a system that allows cheap workers to commit, push, deploy, or read secrets

---

## 4. Product Thesis

The correct design is not:

```text
Codex native subagents + custom config.toml magic + one hardcoded DeepSeek worker
```

The correct design is:

```text
Codex
  -> CodexSaver MCP
  -> internal worker orchestration
  -> verifier + aggregation
  -> Codex final judgment
```

This keeps the risky part stable:

- Codex only needs one reliable MCP tool surface
- CodexSaver can evolve internally without depending on Codex internals
- worker provider strategy can change independently of the Codex app or CLI

---

## 5. Architecture

```text
User
  ↓
Codex (planner / reviewer / final authority)
  ↓
CodexSaver MCP Server
  ├─ Intent Router
  ├─ Work Graph Planner
  ├─ Specialist Registry
  ├─ Worker Orchestrator
  │   ├─ readonly workers
  │   ├─ bounded patch workers
  │   └─ repair workers
  ├─ Sandbox Runner
  ├─ Verifier Gate
  ├─ Patch Aggregator
  ├─ Evidence Reporter
  └─ Benchmark / Cost Ledger
  ↓
Local Agent Card workers
  ├─ Pi Agent (default)
  ├─ optional Aider agent
  ├─ optional Claude Code agent
  └─ custom local workers
  ↓
Codex receives verified evidence
  ↓
Codex applies / revises / commits
```

---

## 6. Design Principles

### 6.1 Codex remains the judge

Workers may suggest, patch, explain, and test.
Only Codex decides whether the result is accepted.

### 6.2 Boundaries before intelligence

The key reliability primitive is not prompt cleverness.
It is explicit boundaries:

- allowed files
- forbidden paths
- allowlisted commands
- output schema
- max diff lines
- max iterations

### 6.3 Parallelize only where independence is real

Do not parallelize work that writes to the same files or needs tight sequential reasoning.
Prefer:

- docs + tests + explanation in parallel
- implementation + explanation in parallel
- multi-file independent fixture generation in parallel

Avoid:

- two workers editing the same file without merge strategy
- high-risk logic split across cheap workers

### 6.4 Verification is mandatory

No worker output reaches Codex as a success unless it passes deterministic checks.

### 6.5 Metrics decide routing policy

v3 is not complete when it "feels smart."
It is complete when it produces measurable gains:

- higher success rate
- lower Codex token usage
- lower rewrite rate by Codex
- stable patch verification pass rate

### 6.6 Guidance should be opt-in and project-local first

v3 should help Codex prefer CodexSaver for the right tasks, but should avoid
surprising global mutations.

Preferred order:

1. project-local `AGENTS.md` guidance
2. optional project-local hook scaffolding
3. optional project-local `.codex/config.toml` feature flags
4. avoid modifying unrelated global config by default

This is why v3 supports profiles such as:

- `basic`: AGENTS guidance only
- `full`: AGENTS guidance + hook scaffolding + local hook feature enablement

The default should remain minimally invasive.

---

## 7. Execution Model

v3 introduces a **work graph** rather than a single work packet.

### 7.1 Work Graph

Each request becomes a DAG of nodes:

- `research`
- `explain`
- `test`
- `docs`
- `format`
- `bounded_patch`
- `review_hint`

Each node has:

- node id
- goal
- type
- dependencies
- allowed files
- forbidden paths
- allowed commands
- specialist profile
- expected output type

Example:

```json
{
  "graph_id": "task-123",
  "nodes": [
    {
      "id": "impl",
      "type": "bounded_patch",
      "goal": "Implement login(username, password)",
      "depends_on": [],
      "specialist": "impl_worker",
      "allowed_files": ["src/user-auth.js"],
      "allowed_commands": []
    },
    {
      "id": "tests",
      "type": "bounded_patch",
      "goal": "Add unit tests for login(username, password)",
      "depends_on": ["impl"],
      "specialist": "test_writer",
      "allowed_files": ["tests/user-auth.test.js"],
      "allowed_commands": ["npm test -- user-auth"]
    },
    {
      "id": "docs",
      "type": "bounded_patch",
      "goal": "Add JSDoc for login(username, password)",
      "depends_on": ["impl"],
      "specialist": "doc_writer",
      "allowed_files": ["src/user-auth.js"],
      "allowed_commands": []
    }
  ]
}
```

### 7.2 Execution Modes

| Mode | Description | Typical use |
|------|-------------|-------------|
| `readonly_parallel` | multiple read-only workers in parallel | explanation, scanning, perf hints |
| `bounded_patch_parallel` | multiple patch workers on disjoint write sets | docs/tests/fixtures |
| `map_reduce` | fan out analysis, then aggregate | large repo understanding |
| `repair_loop` | retry same node within fixed budget | patch apply or check failures |
| `codex_takeover` | stop worker execution and return to Codex | ambiguity, policy conflict, merge conflict |

---

## 8. Specialist Registry

v3 should not rely on `~/.codex/config.toml` to define named subagents.
CodexSaver should own a dedicated registry.

Recommended location:

```text
~/.codexsaver/agents.toml
```

Optional project override:

```text
.codexsaver/agents.toml
```

Example:

```toml
[orchestrator]
max_parallel_workers = 4
max_repair_rounds = 2
fallback_to_codex_on_conflict = true

[workers.impl_worker]
provider = "pi-agent"
model = "pi-agent-default"
mode = "bounded_patch"
prompt_file = "~/.codexsaver/prompts/impl_worker.md"

[workers.test_writer]
provider = "pi-agent"
model = "pi-agent-default"
mode = "bounded_patch"
prompt_file = "~/.codexsaver/prompts/test_writer.md"

[workers.doc_writer]
provider = "pi-agent"
model = "pi-agent-default"
mode = "bounded_patch"
prompt_file = "~/.codexsaver/prompts/doc_writer.md"

[workers.explainer]
provider = "pi-agent"
model = "pi-agent-default"
mode = "readonly"
prompt_file = "~/.codexsaver/prompts/explainer.md"

[workers.perf_reviewer]
provider = "pi-agent"
model = "pi-agent-default"
mode = "readonly"
prompt_file = "~/.codexsaver/prompts/perf_reviewer.md"
```

Each specialist has:

- `provider`
- `model`
- `mode`
- `prompt_file`
- `timeout_sec`
- `max_output_tokens`
- `allowed_output_type`
- optional `reasoning_effort`

---

## 9. Routing Model

### 9.1 High-Level Routes

| Route | Meaning |
|------|---------|
| `codex_only` | task is too risky or too ambiguous |
| `single_worker` | v2-style bounded execution is enough |
| `multi_worker` | v3 fan-out is beneficial |
| `readonly_swarm` | parallel understanding only |

### 9.2 Risk Classes

| Risk | Meaning | Default route |
|------|---------|---------------|
| `R0` | read-only understanding | multi-worker allowed |
| `R1` | bounded docs/tests/fixtures | multi-worker allowed |
| `R2` | small isolated implementation | single worker or controlled fan-out |
| `R3` | sensitive logic, shared write surface | Codex primary |
| `R4` | auth/security/payment/migration/deploy | Codex only |

### 9.3 Multi-Worker Eligibility Rules

v3 may fan out only when all are true:

- task decomposition is clear
- subproblems have disjoint or merge-safe outputs
- no forbidden path is involved
- no secrets are needed
- each subtask has a bounded verification story

---

## 10. MCP Interface

v3 keeps existing v2 tools and adds orchestration tools.

### Existing tools retained

- `codexsaver.delegate_task`
- `codexsaver.delegate_work_packet`

### New tools

#### `codexsaver.orchestrate_task`

High-level entrypoint for v3.

Input:

```json
{
  "goal": "Implement login(username, password), add tests, add docs, and explain risk",
  "files": ["src/user-auth.js"],
  "workspace": "/repo",
  "constraints": [],
  "max_parallel_workers": 4,
  "dry_run": false
}
```

Output:

```json
{
  "route": "multi_worker",
  "status": "success | needs_codex | dry_run | failed",
  "summary": "Implementation, tests, and docs completed through 3 workers.",
  "graph": {},
  "results": [],
  "aggregate_patch": "unified diff",
  "checks": [],
  "verification": {},
  "metrics": {},
  "estimated_savings_percent": 58
}
```

#### `codexsaver.run_specialist`

Low-level explicit specialist execution tool.

Input:

```json
{
  "specialist": "test_writer",
  "goal": "Add tests for parse_config()",
  "files": ["src/config.py"],
  "allowed_files": ["tests/test_config.py"],
  "allowed_commands": ["pytest tests/test_config.py -q"],
  "workspace": "/repo"
}
```

Output shape follows the v2 work packet result contract.

---

## 11. Node Lifecycle

Each graph node moves through:

```text
pending
  -> running
  -> patch_proposed
  -> checks_running
  -> verified
  -> merged
```

Failure states:

```text
rejected
repairing
needs_codex
failed
```

Rules:

- a node cannot merge unless verified
- a node cannot run if dependencies are not merged or declared read-only complete
- a node exceeding retry budget becomes `needs_codex`

---

## 12. Sandbox & Verification

v3 extends the v2 verifier, not replaces it.

### 12.1 Per-Node Sandbox

Each write-capable node gets its own temp workspace copy.

Benefits:

- isolation
- deterministic checks
- no shared corruption between workers
- easy patch extraction

### 12.2 Verification Gates

For every patch-producing node:

- changed files are within `allowed_files`
- no `forbidden_paths` touched
- unified diff applies cleanly
- diff lines do not exceed budget
- allowlisted checks pass
- no secrets in patch
- no protected path keywords

### 12.3 Preflight

If a node's allowlisted checks already pass without any changes, return:

```json
{
  "status": "success",
  "preflight_satisfied": true
}
```

This is especially useful for:

- version metadata already present
- docs already updated
- generated fixtures already in place

---

## 13. Patch Aggregation

Aggregation is the core new risk in v3.

### 13.1 Merge Policy

Safe to auto-aggregate:

- disjoint file sets
- append-only docs/test files
- non-overlapping hunks in the same file after structural check

Unsafe to auto-aggregate:

- overlapping hunks in same file
- worker disagreement on same logic region
- any patch that changes protected domains

### 13.2 Aggregation Output

The aggregator should emit:

- `aggregate_patch`
- `per_node_patches`
- `merge_conflicts`
- `codex_review_notes`

If there is any conflict:

```text
do not guess
return needs_codex with conflict summary
```

---

## 14. Cost Model

v3 should distinguish four cost buckets:

- orchestrator planning cost
- worker generation cost
- repair cost
- verification command cost

### 14.1 Budget-Aware Dispatch

Planner should use:

- `max_parallel_workers`
- `max_total_worker_calls`
- `max_repair_rounds`
- optional `max_estimated_cost_index`

### 14.2 Metrics To Track

- eligible multi-worker tasks
- multi-worker success rate
- average workers per task
- repair rate per specialist
- merge conflict rate
- Codex rewrite rate after aggregation
- cost index vs single-worker baseline

---

## 15. Benchmark Strategy

v3 claims should be proved with repeatable benchmarks, not slogans.

### 15.1 Benchmark Suites

- docs-only tasks
- tests-only tasks
- implementation + tests
- implementation + docs + explanation
- read-only analysis tasks

### 15.2 Required Comparisons

Compare:

1. Codex only
2. CodexSaver v2 single worker
3. CodexSaver v3 multi-worker

Track:

- success rate
- wall-clock latency
- check pass rate
- estimated cost index
- Codex rewrite frequency

### 15.3 v3 Success Criteria

Suggested targets:

- worker-orchestrated success rate >= v2
- lower average cost index than v2 on composite tasks
- lower latency than v2 on decomposable tasks
- no regression in protected-path safety

---

## 16. Failure Modes

v3 must explicitly handle:

### 16.1 Fan-Out Waste

Too many workers launched for a trivial task.

Mitigation:

- planner threshold
- dry-run graph preview
- budget caps

### 16.2 Duplicate Work

Two workers solve the same thing.

Mitigation:

- disjoint write ownership
- node-level file ownership

### 16.3 Merge Conflicts

Multiple patches touch same file region.

Mitigation:

- pre-assign ownership
- codex takeover on conflict

### 16.4 Weak Specialist Fit

Wrong worker selected for task type.

Mitigation:

- explicit specialist registry
- success-rate tracking by worker type

### 16.5 Repair Loop Explosion

Workers repeatedly fail and retry.

Mitigation:

- hard iteration caps
- compact failure feedback
- fallback to Codex

---

## 17. Security Model

Workers never:

- access secrets directly
- push commits
- deploy
- run arbitrary shell
- fetch arbitrary network resources

Only Codex or an explicitly approved local operator can do those things.

This preserves the core trust boundary:

```text
cheap model = bounded labor
expensive model = judgment and authority
```

---

## 18. Migration From v2

v3 should be additive.

### 18.1 Keep v2 Stable

Do not break:

- `delegate_task`
- `delegate_work_packet`
- sandbox semantics
- verifier contract

### 18.2 Build v3 On Top

v3 should compose v2 primitives:

- a v3 node is essentially a v2 work packet plus specialist metadata
- the v3 aggregator consumes multiple v2-style node results

### 18.3 Suggested Delivery Order

#### Phase 1

- specialist registry
- readonly parallel orchestration
- benchmark ledger for v3

#### Phase 2

- bounded patch parallel on disjoint files
- aggregation layer
- conflict detection

#### Phase 3

- adaptive routing
- provider scoring
- cost-aware planner

---

## 19. Implementation Plan

### 19.1 New Modules

Recommended additions:

- `codexsaver/orchestrator.py`
- `codexsaver/specialists.py`
- `codexsaver/work_graph.py`
- `codexsaver/aggregator.py`
- `codexsaver/ledger.py`

### 19.2 MCP Additions

- extend `codexsaver_mcp.py`
- add schemas for `orchestrate_task` and `run_specialist`

### 19.3 Test Additions

- planner tests
- specialist registry tests
- aggregation tests
- conflict detection tests
- multi-worker benchmark smoke tests

---

## 20. Open Questions

These should remain explicit until implementation:

1. Should v3 aggregate into a single unified patch or return a patch bundle first?
2. Should repair loops happen per node only, or also after aggregation?
3. Should explanation/perf specialists be pure read-only workers or allowed to annotate files?
4. Should there be a local agent fallback chain when Pi Agent fails?
5. Should the cost ledger be persisted locally in JSON, SQLite, or plain benchmark artifacts?

---

## 21. Project Guidance Layer

To make Codex call CodexSaver more reliably for low-risk tasks, v3 includes a
project guidance layer.

### 21.1 AGENTS Guidance

CodexSaver may install a managed block into project-root `AGENTS.md` that:

- prioritizes `codexsaver.orchestrate_task` for decomposable low-risk work
- prioritizes `codexsaver.run_specialist` for explicit explanation/tests/docs tasks
- preserves Codex-only handling for auth, security, payment, migrations, and ambiguity

The install must be managed and replaceable, not a destructive overwrite.

### 21.2 Optional Hooks

Hooks are more invasive and may depend on Codex hook support being enabled.
Therefore they should be opt-in.

Hooks should be advisory, not authority-bearing.

Recommended use:

- `UserPromptSubmit` prompt enrichment that reminds Codex to prefer CodexSaver for low-risk work

Avoid:

- assuming hook coverage for every tool type
- hard-blocking unrelated user flows

### 21.3 Profile-Based Install

Recommended CLI:

```text
codexsaver superpower install --profile basic
codexsaver superpower install --profile full
```

Behavior:

- `basic`: install AGENTS guidance only
- `full`: install AGENTS guidance, project-local hook scaffolding, and local `codex_hooks` feature enablement

This keeps the system configurable without forcing invasive setup on every user.

---

## 22. v3.5/v3.6 Refinements

### 22.1 Verified Patch Orchestration

Patch-producing nodes must return a public handoff schema rather than loose text:

- `intent`
- `changed_files`
- `patch`
- `verification_plan`
- `rollback_notes`
- `risk_notes`

Before aggregation, CodexSaver runs patch lint:

- the patch must be non-empty
- `changed_files` must match files touched by the diff
- no two nodes in the same batch may write the same file
- the patch must stay inside `allowed_files`
- the patch must apply cleanly in a sandbox

Failed patch nodes should get a bounded node-level repair attempt before the
whole graph returns `needs_codex`.

Repairable patch-lint failures should get the same bounded node-level retry:

- `changed_files` mismatch
- missing `verification_plan`
- missing `rollback_notes`
- patch apply failure during lint replay
- specialist-specific metadata failures such as weak `test_writer` verification

Non-repairable failures, such as duplicate file writes inside the same batch,
should still return `needs_codex` immediately.

`test_writer` should be stricter than generic patch nodes:

- Python tests must modify at least one `tests/test_*.py` file
- `verification_plan` must include the exact generated test file in a `pytest` command
- `rollback_notes` must explain how to delete or revert the generated test file

Worker metrics should include `repair_count` so benchmarks can distinguish
first-pass patch success from bounded repair success.

### 22.2 Agent Card Discovery

v3.6 uses Agent Card files as the minimal worker registration format.
CodexSaver scans:

- `.pi-agents/*.agent-card.json`
- `.pi/agents/*.agent-card.json`
- `~/.codexsaver/agents/*.agent-card.json`

The builtin Pi Agent card is always available as a safe default. This keeps the
system useful with zero configuration while allowing users to add more workers
without editing Codex config.

v3.6 should not silently fall back to DeepSeek for v3 worker execution. If the
Pi Agent command is unavailable, the live node returns `needs_codex`; DeepSeek
remains an optional provider-backed lane for earlier delegation tools.

### 22.3 Weighted Worker Routing

Worker selection is score-based:

| Dimension | Weight |
|---|---:|
| Capability match | `0.40` |
| Historical success | `0.25` |
| Cost weight | `0.20` |
| Current load | `0.10` |
| Context fit | `0.05` |

The router still obeys the existing safety policy first. Scoring only happens
after a task or node is considered safe enough to delegate.

### 22.4 Task Lifecycle

Every delegated node should expose a task ID and A2A-compatible state flow:

```text
submitted -> running -> completed
                  -> failed
                  -> timed_out
```

This is intentionally smaller than a full A2A implementation, but keeps the
semantic upgrade path open.

---

## 23. Final Position

v3 is feasible and strategically strong, but only if implemented in the right layer.

The winning design is:

- **not** unstable Codex-native subagent config as the primary dependency
- **yes** CodexSaver-owned orchestration, registry, verification, and aggregation

That gives CodexSaver a durable architecture:

- Codex remains the premium reasoning layer
- Pi Agent and local workers do more real work
- verification keeps the system honest
- metrics decide whether the orchestration is actually better

For the next patch-success phase, the most important proof is not just readonly
throughput. It is whether bounded patch workers can recover from fixable output
mistakes without losing safety. That means:

- repairable lint failures should be retried locally, not escalated immediately
- `test_writer` should have hard validation for file path, pytest command, and rollback
- duplicate writes and unsafe patches should remain blocked
- benchmark reports should measure both write success rate and verified outcome rate

**Final slogan**

_More workers. Same judgment. Lower cost._
