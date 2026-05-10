# CodexSaver v2 — Spec Document

> **Codex decides. Worker implements. Verifier gates. Codex reviews.**

---

## 1. Concept & Vision

CodexSaver v2 is a **bounded coding-agent engine** for Codex. It is not a simple delegation tool — it is a controlled implementation loop where a worker model can read, modify, test, and repair within explicit boundaries, while Codex retains judgment, review, and commit authority.

**Slogan:** _DeepSeek does the work. Codex makes the decisions._

v1 was: `delegate_task → worker returns JSON patch`

v2 is: `delegate_work_packet → worker runs a bounded loop → returns patch + evidence`

---

## 2. Architecture

```
User
  ↓
Codex (judgment + review)
  ↓
CodexSaver MCP Server
  ├─ Router              (delegation level)
  ├─ Work Packet Builder  (bounded contract)
  ├─ Context Planner     (what to show worker)
  ├─ Worker Runtime      (ACI loop)
  │   ├─ ACI Tools
  │   ├─ Iteration Loop
  │   └─ Patch Builder
  ├─ Verifier Gate       (deterministic safety checks)
  ├─ Evidence Reporter   (structured output)
  └─ Metrics Store       (observability)
  ↓
Codex Review → Apply → Commit
```

---

## 3. Delegation Levels

| Level | Name | When to use |
|-------|------|-------------|
| L0 | Codex only | architecture, auth, payment, security, migrations, ambiguous tasks |
| L1 | Research | protected domain explanation, repo scan, impact analysis |
| L2 | Draft patch | README/docs, tests, fixtures, boilerplate |
| L3 | Bounded implementation | isolated utility changes, provider adapters, CLI flags, formatting, small refactors |
| L4 | Repair loop | L3 + allowed test command + max_iterations (2–3 rounds) |

---

## 4. Work Packet Contract

### Input: `DelegateWorkPacketInput`

```json
{
  "goal": "Add Anthropic provider support",
  "workspace": "/repo",
  "task_type": "bounded_implementation",
  "files": ["codexsaver/provider.py"],
  "constraints": [],
  "acceptance_criteria": [
    "Anthropic Messages API is supported",
    "OpenAI-compatible providers still work",
    "Provider tests pass"
  ],
  "delegation_level": "bounded_impl",
  "allowed_files": [
    "codexsaver/provider.py",
    "tests/test_provider.py"
  ],
  "forbidden_paths": [
    ".github/**", "deploy/**", "auth/**", "payment/**"
  ],
  "allowed_commands": ["pytest tests/test_provider.py -q"],
  "max_iterations": 3,
  "max_diff_lines": 300,
  "dry_run": false
}
```

### Output: `DelegateWorkPacketOutput`

```json
{
  "route": "worker | codex",
  "status": "success | needs_codex | failed | dry_run",
  "delegation_level": "bounded_impl",
  "summary": "Added Anthropic Messages API provider path.",
  "changed_files": ["codexsaver/provider.py", "tests/test_provider.py"],
  "patch": "unified diff",
  "checks": [
    {
      "command": "pytest tests/test_provider.py -q",
      "exit_code": 0,
      "summary": "5 passed"
    }
  ],
  "verification": {
    "ok": true,
    "fallback_to_codex": false,
    "warnings": [],
    "reason": "All gates passed."
  },
  "metrics": {
    "iterations": 2,
    "worker_actions": 8,
    "estimated_savings_percent": 55
  }
}
```

---

## 5. ACI (Agent-Computer Interface)

Worker uses structured tools, not raw shell. This is the core reliability difference from v1.

### Recommended ACI Tools

| Tool | Purpose |
|------|---------|
| `search_code(pattern, path?)` | Find code occurrences |
| `open_file(path, line?, limit=120)` | Read bounded file content |
| `list_files(glob)` | List files matching pattern |
| `propose_patch(unified_diff)` | Submit a diff for sandboxed application |
| `run_check(command_id)` | Execute an allowlisted check |
| `finish(summary, patch, evidence)` | Signal completion |
| `escalate(reason)` | Hand back to Codex |

### Explicitly Forbidden

```
arbitrary_shell(command)
git commit / git push
rm -rf
network fetch (unless read-only docs mode)
secret read
deploy commands
```

---

## 6. Execution Loop

```
1. Codex sends Work Packet
2. Worker reads goal + allowed files
3. Worker searches or opens context files
4. Worker proposes patch
5. Sandbox applies patch in isolation
6. Verifier runs quick checks
7. If checks fail → compact failure output fed back to worker
8. Worker repairs, up to max_iterations
9. Verifier final gate check
10. Codex receives patch + evidence
```

```python
for i in range(packet.max_iterations):
    action = worker.next_action(observation)

    match action.type:
        case "search_code":
            observation = aci.search(action.pattern)
        case "open_file":
            observation = aci.open_file(action.path, action.line)
        case "propose_patch":
            result = sandbox.try_patch(action.patch)
            observation = verifier.quick_check(result)
        case "run_check":
            observation = checks.run_allowed(action.command_id)
        case "finish":
            return verifier.finalize(action)
        case "escalate":
            return codex_takeover(action.reason)

return codex_takeover("max_iterations_exceeded")
```

---

## 7. Verifier Gates

All must pass for output to reach Codex:

```
Path Gate:        changed_files ⊆ allowed_files
Risk Gate:        forbidden paths untouched
Patch Gate:       unified diff parses, applies cleanly, diff_lines ≤ max_diff_lines
Command Gate:     only allowed command IDs executed
Secret Gate:      no API keys / tokens in patch
Dependency Gate:  no lockfile/pyproject changes unless explicitly allowed
Test Gate:        required checks pass or return needs_codex
Iteration Gate:   max_iterations hard stop
```

---

## 8. Permission Model

| Category | Worker | Codex |
|----------|--------|-------|
| Read | bounded by context planner | full |
| Write | patch only, allowed_files only | full |
| Execute | allowed_commands only (by ID) | full |
| Git | none | stage / commit / push |
| Network | none (read-only docs optional) | full |
| Secrets | never | full |

Worker **never** writes directly to filesystem. All modifications go through `propose_patch → sandbox → verifier`.

---

## 9. Context Planner

Not everything goes to the worker. Context planner selects:

- Explicit files from Codex instruction
- Router-discovered related files
- Nearby test files
- `pyproject.toml` / `package.json` config
- README / SPEC only when docs task

Rule: **small context, enough to act.**

---

## 10. Metrics & Observability

```text
delegated_work_packets
worker_success_rate
codex_takeover_rate
average_iterations
test_pass_rate
patch_rejection_rate
estimated_savings_percent
protected_path_blocks
max_iteration_blocks
```

Key ratio to track:

```
worker_successfully_completed / eligible_work_packets
```

and:

```
Codex manual edit rate after worker patch
```

If Codex frequently rewrites worker patches, the worker isn't truly doing more work.

---

## 11. Progressive Roadmap

**Phase 1: Work Packet Contract**
- `DelegateWorkPacketInput` / `Output` schemas
-强化 `allowed_files` / `acceptance_criteria` / `checks`
- Codex still calls worker in one shot

**Phase 2: ACI Read Tools**
- `search_code`, `open_file`, `list_files`
- Worker gets multi-step context reading

**Phase 3: Patch Sandbox**
- `propose_patch` → sandbox apply → diff size / path verification

**Phase 4: Check + Repair Loop**
- `run_check(command_id)` → failure output fed back to worker
- `max_iterations=2–3`

**Phase 5: Metrics + Policy**
- delegation level routing
- success metrics collection
- route tuning

**Phase 6: Optional LLM Evaluator**
- Quality advisory only
- Never approves high-risk patches
- Does not replace deterministic verifier

---

## 12. Product Interface

### v1 tool (preserved)
```
codexsaver.delegate_task
```
One-shot delegation, Codex reviews patch.

### v2 tool (new)
```
codexsaver.delegate_work_packet
```

Tool description:

> Delegate a bounded coding work packet to a configured worker model. Use when the task has clear scope, allowed files, acceptance criteria, and verifiable checks. The worker may inspect files, propose patches, and run allowlisted checks, but cannot commit, deploy, or touch forbidden paths.

---

## 13. Codex vs Worker vs Verifier Responsibilities

### Codex does
- Clarify intent
- Choose delegation level
- Define allowed files and acceptance criteria
- Review final patch
- Apply changes
- Commit
- Handle high-risk judgment

### Worker does
- Inspect bounded context
- Search relevant code
- Propose patch
- Write/update tests
- Run allowed checks
- Repair failed checks within limit
- Escalate when blocked

### Verifier does
- Enforce all gates deterministically
- Run commands and capture evidence
- Block unsafe output
- Produce structured evidence for Codex review

---

## 14. Design Principles

1. **Expand worker action space, not worker final authority.** More work gets done; Codex still decides.
2. **ACI over raw shell.** Structured tools > unbounded commands. (SWE-agent lesson.)
3. **Verifier is deterministic, not LLM-judged.** Safety gates must be code, not intuition.
4. **Metrics before optimization.** Measure `worker_successfully_completed / eligible_work_packets` before claiming savings.
5. **Fail fast and escalate.** One `needs_codex` return → Codex takes over. No retry loops burning tokens.
6. **Worker writes nothing directly.** All modifications go through `propose_patch → sandbox → verifier`. No side effects.

---

## 15. File Structure (v2)

```
codexsaver/
├── __init__.py
├── schema.py           # v1 + v2 input/output schemas
├── router.py          # delegation level routing
├── context.py         # context planner
├── engine.py          # main orchestration
├── verifier.py        # deterministic gates
├── cost.py            # savings estimation
│
├── v2/
│   ├── __init__.py
│   ├── work_packet.py    # DelegateWorkPacketInput / Output
│   ├── aci.py           # ACI tool definitions
│   ├── runtime.py       # worker execution loop
│   ├── sandbox.py       # patch application sandbox
│   ├── checks.py        # allowed command runner
│   └── metrics.py      # observability
│
├── codexsaver_mcp.py  # MCP server (v1 + v2 tools)
├── cli.py
├── .codex/config.toml
├── AGENTS.md
└── README.md
```

---

## 16. Out of Scope (v2 MVP)

- Multi-worker orchestration
- Learning-based routing
- Web dashboard
- Direct git operations by worker
- Network access by worker (beyond read-only docs)
- LLM-based verification

---

_This spec defines CodexSaver v2 as a managed worker architecture — not a multi-agent chat, but a bounded loop with a primary controller (Codex), a constrained executor (Worker), and a deterministic gate (Verifier)._
