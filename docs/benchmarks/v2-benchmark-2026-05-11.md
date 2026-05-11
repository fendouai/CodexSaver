# CodexSaver v2 Benchmark

Date: 2026-05-11

Method: Codex-only is a normalized counterfactual baseline with cost index 1.00. CodexSaver results are real bounded work-packet runs through the configured worker provider.

| Task | Kind | Codex-only cost | CodexSaver status | CodexSaver cost | Savings | Effect | Latency |
|---|---|---:|---|---:|---:|---:|---:|
| Create v2 smoke doc | docs | 1.00 | success (worker) | 0.55 | 45% | 1.0 | 2.36s |
| Add generated cost test | tests | 1.00 | success (worker) | 0.55 | 45% | 1.0 | 9.30s |
| Add package version metadata | small_code | 1.00 | success (preflight) | 0.00 | 100% | 1.0 | 0.03s |
| Document work-packet CLI | docs | 1.00 | success (worker) | 0.55 | 45% | 1.0 | 3.86s |
| Create Chinese v2 note | zh_docs | 1.00 | success (worker) | 0.55 | 45% | 1.0 | 2.68s |
