# CodexSaver v3.6 Patch Success Benchmark — 2026-05-31

Deterministic patch benchmark. Each scenario replays fixed worker outputs against the current orchestrator and compares them with a simulated pre-fix v3.5 baseline. This isolates orchestration robustness rather than live model variance.

## Summary

- `scenarios`: `5`
- `baseline_write_successes`: `2`
- `current_write_successes`: `4`
- `baseline_write_success_rate`: `0.4`
- `current_write_success_rate`: `0.8`
- `baseline_verified_outcomes`: `1`
- `current_verified_outcomes`: `5`
- `baseline_verified_outcome_rate`: `0.2`
- `current_verified_outcome_rate`: `1.0`
- `verified_outcome_gain`: `4`
- `average_repair_count`: `0.8`
- `average_latency_seconds`: `0.147`

## Results

| Scenario | Baseline status | Baseline verified outcome | Current status | Current verified outcome | Repair count | Delta |
|---|---|---:|---|---:|---:|---:|
| Node repair after initial patch failure | `success` | 1 | `success` | 1 | 1 | +0 |
| Lint repair for changed_files mismatch | `needs_codex` | 0 | `success` | 1 | 1 | +1 |
| Lint repair for missing verification plan | `needs_codex` | 0 | `success` | 1 | 1 | +1 |
| test_writer exact pytest path repair | `success` | 0 | `success` | 1 | 1 | +1 |
| Duplicate file writes remain blocked | `needs_codex` | 0 | `needs_codex` | 1 | 0 | +1 |

## Interpretation

- `write_success_rate` measures how many scenarios ended in a successful worker-produced patch.
- `verified_outcome_rate` is broader: it also counts scenarios where CodexSaver correctly preserved a safety block instead of producing an unsafe patch.
- The largest gain comes from lint-repair: fixable metadata and verification mistakes no longer force an immediate return to Codex.
- `test_writer` is now stricter: weak pytest plans do not count as verified success unless the exact generated test file is covered.
- Duplicate writes remain blocked on purpose. This benchmark treats that as preserved safety, not lost capability.
- The benchmark is deterministic and isolates orchestrator behavior, so it should be used alongside live Pi Agent benchmarks rather than instead of them.
