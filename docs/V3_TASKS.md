# CodexSaver v3 — Development Task List

This document turns [SPEC_v3.md](./SPEC_v3.md) into an implementation queue.

---

## Phase 0: Foundation

Goal: create stable v3 entrypoints and internal abstractions without breaking v2.

- [x] Add `docs/SPEC_v3.md`
- [x] Add `codexsaver.orchestrate_task` engine entrypoint
- [x] Add `codexsaver.run_specialist` engine entrypoint
- [x] Add specialist registry skeleton
- [x] Add work graph planner skeleton
- [x] Add patch aggregator skeleton
- [x] Add ledger skeleton
- [x] Add CLI/MCP preview hooks for v3 planning
- [x] Add README links and v3 preview docs
- [x] Add optional project guidance installer with `basic` and `full` profiles

Acceptance:

- v2 tools still work unchanged
- v3 dry-run planning returns a graph preview
- new modules are covered by baseline tests

---

## Phase 1: Read-Only Orchestration

Goal: execute parallel read-only specialists safely.

- [x] Implement readonly specialist executor
- [x] Add `explainer` and `perf_reviewer` execution path
- [x] Add fan-out + gather flow for read-only nodes
- [x] Add readonly aggregation output format
- [x] Add benchmarks for explain/risk/perf tasks

Acceptance:

- `orchestrate_task` can complete read-only graphs end-to-end
- parallel readonly tasks are faster than sequential v2 baseline
- no filesystem write path is exercised

---

## Phase 2: Bounded Patch Parallel

Goal: allow multiple specialists to produce verified patches on disjoint file sets.

- [x] Convert a work-graph node into a v2 work packet
- [x] Execute bounded patch nodes through isolated sandboxes
- [x] Enforce node-level file ownership
- [x] Aggregate disjoint patches into one output
- [x] Reject overlapping writes with `needs_codex`
- [x] Add tests for disjoint merge success
- [x] Add tests for overlap conflict failure
- [x] Add pre-aggregation patch lint for empty, mismatched, duplicate, and non-applying patches

Acceptance:

- docs/tests/fixtures can run as parallel nodes
- aggregated patch is deterministic
- overlap returns conflict summary instead of guessing

---

## Phase 3: Repair and Retry

Goal: make node-level repair loops practical and bounded.

- [x] Add per-node repair budget
- [x] Feed compact verifier failures back into the same specialist
- [x] Track repair counts in metrics
- [x] Add tests for apply failure -> repair success
- [x] Add tests for lint repair -> success
- [ ] Add tests for retry exhaustion -> `needs_codex`

Acceptance:

- repair is local to the failing node
- successful repair improves node completion rate
- retry exhaustion never escapes configured limits

---

## Phase 4: Cost and Benchmarking

Goal: measure whether v3 is actually better than v2.

- [ ] Add persistent benchmark ledger format
- [x] Add v3 benchmark runner
- [ ] Compare Codex-only vs v2 vs v3
- [x] Track worker count, repair count, latency, merge conflicts
- [x] Add deterministic patch-success benchmark for lint repair and `test_writer` validation
- [ ] Track Codex rewrite rate after aggregation

Acceptance:

- benchmark reports can be regenerated
- v3 claims are backed by repo-local artifacts
- cost numbers are clearly labeled as estimated or measured

---

## Phase 5: Adaptive Routing

Goal: make orchestration choose the right strategy automatically.

- [x] Add specialist success-rate scoring
- [x] Add Agent Card discovery from `.pi-agents/`, `.pi/agents`, and `~/.codexsaver/agents`
- [x] Add weighted worker scoring for capability, history, cost, load, and context
- [x] Add A2A-compatible task lifecycle metadata
- [ ] Add provider fallback policy
- [ ] Add route scoring for single-worker vs multi-worker
- [ ] Add budget caps for fan-out
- [ ] Add heuristics for task decomposition quality

---

## Phase 6: Guidance Layer

Goal: bias Codex toward CodexSaver without over-mutating user config.

- [x] Add managed `AGENTS.md` block installer
- [x] Add optional hook scaffold installer
- [x] Add optional local `.codex/config.toml` feature enablement
- [x] Expose `basic` vs `full` installation profiles
- [ ] Add doctor/reporting for profile health and hook readiness

Acceptance:

- `basic` only modifies project-root `AGENTS.md`
- `full` modifies project-local files only
- rerunning installation updates managed blocks instead of duplicating them

Acceptance:

- planner can decline multi-worker mode when decomposition is weak
- poor specialists are deprioritized automatically
- cost caps prevent runaway fan-out

---

## Module Ownership

- `codexsaver/orchestrator.py`: v3 entrypoint, route selection, top-level coordination
- `codexsaver/work_graph.py`: graph planning and node generation
- `codexsaver/specialists.py`: specialist registry and profile resolution
- `codexsaver/aggregator.py`: patch/result aggregation and conflict detection
- `codexsaver/ledger.py`: benchmark and cost summaries
- `codexsaver/work_packet.py`: v2 execution primitive reused by v3 nodes
- `codexsaver/agent_registry.py`: v3.6 Agent Card discovery and builtin Pi Agent card
- `codexsaver/agent_router.py`: v3.6 weighted worker scoring
- `codexsaver/task_lifecycle.py`: v3.6 task ID and status flow
- `codexsaver/engine.py`: public API surface for CLI/MCP

---

## Immediate Next Milestone

Recommended next coding milestone:

1. Enforce node-level ownership and richer conflict semantics beyond `changed_files`.
2. Add per-node repair metrics and durable ledger persistence.
3. Replace the builtin Agent Card with real `pi-side-agents` subprocess dispatch behind the same routing interface.
