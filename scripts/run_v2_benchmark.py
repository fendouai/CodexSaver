#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from codexsaver.engine import CodexSaverEngine


TASKS: List[Dict[str, Any]] = [
    {
        "name": "Create v2 smoke doc",
        "kind": "docs",
        "goal": "Create docs/v2-smoke.md with one sentence: CodexSaver v2 runs bounded worker patches in a sandbox.",
        "files": ["README.md"],
        "allowed_files": ["docs/v2-smoke.md"],
        "acceptance_criteria": ["docs/v2-smoke.md exists in sandbox"],
        "allowed_commands": [
            "python -c \"from pathlib import Path; assert Path('docs/v2-smoke.md').exists()\""
        ],
        "max_diff_lines": 80,
    },
    {
        "name": "Add generated cost test",
        "kind": "tests",
        "goal": "Create tests/test_cost_generated.py with one pytest test proving CostEstimator returns 45 for a tiny delegated WorkerTask.",
        "files": ["codexsaver/cost.py", "codexsaver/schema.py", "tests/test_cost.py"],
        "allowed_files": ["tests/test_cost_generated.py"],
        "acceptance_criteria": ["pytest for the generated test passes"],
        "allowed_commands": [
            "python -m pytest tests/test_cost_generated.py -q"
        ],
        "max_diff_lines": 120,
    },
    {
        "name": "Add package version metadata",
        "kind": "small_code",
        "goal": "Add __version__ = '0.2.0' to codexsaver/__init__.py while preserving the module docstring.",
        "files": ["codexsaver/__init__.py"],
        "allowed_files": ["codexsaver/__init__.py"],
        "acceptance_criteria": ["codexsaver.__version__ equals 0.2.0"],
        "allowed_commands": [
            "python -c \"import codexsaver; assert codexsaver.__version__ == '0.2.0'\""
        ],
        "max_diff_lines": 40,
    },
    {
        "name": "Document work-packet CLI",
        "kind": "docs",
        "goal": "Add one concise bullet to README.md Commands section mentioning python cli.py work-packet for bounded v2 delegation.",
        "files": ["README.md"],
        "allowed_files": ["README.md"],
        "acceptance_criteria": ["README mentions work-packet"],
        "allowed_commands": [
            "python -c \"from pathlib import Path; assert 'work-packet' in Path('README.md').read_text()\""
        ],
        "max_diff_lines": 80,
    },
    {
        "name": "Create Chinese v2 note",
        "kind": "zh_docs",
        "goal": "Create docs/v2-smoke-zh.md with one Chinese sentence: CodexSaver v2 会在沙箱里验证 worker patch。",
        "files": ["README_zh.md"],
        "allowed_files": ["docs/v2-smoke-zh.md"],
        "acceptance_criteria": ["Chinese v2 smoke doc exists in sandbox"],
        "allowed_commands": [
            "python -c \"from pathlib import Path; assert Path('docs/v2-smoke-zh.md').exists()\""
        ],
        "max_diff_lines": 80,
    },
]


def main() -> int:
    engine = CodexSaverEngine()
    results: List[Dict[str, Any]] = []
    for task in TASKS:
        started = time.perf_counter()
        result = engine.delegate_work_packet({
            "goal": task["goal"],
            "files": task["files"],
            "allowed_files": task["allowed_files"],
            "acceptance_criteria": task["acceptance_criteria"],
            "allowed_commands": task["allowed_commands"],
            "workspace": ".",
            "delegation_level": "bounded_impl",
            "max_iterations": 3,
            "max_diff_lines": task["max_diff_lines"],
        })
        elapsed = time.perf_counter() - started
        savings = int(result.get("estimated_savings_percent", 0) or 0)
        success = result.get("status") == "success"
        checks = result.get("checks", [])
        preflight_satisfied = bool(result.get("preflight_satisfied"))
        results.append({
            "name": task["name"],
            "kind": task["kind"],
            "codex_only": {
                "cost_index": 1.0,
                "effect": "counterfactual_baseline",
                "notes": "Codex-only is the normalized baseline; it was not executed as a separate model run.",
            },
            "codexsaver": {
                "route": result.get("route"),
                "status": result.get("status"),
                "execution_mode": "preflight" if preflight_satisfied else "worker",
                "cost_index": 0.0 if preflight_satisfied else round(1 - savings / 100, 2) if success else 1.0,
                "estimated_savings_percent": savings,
                "effect_score": 1.0 if success and all(c.get("exit_code") == 0 for c in checks) else 0.0,
                "latency_seconds": round(elapsed, 2),
                "iterations": result.get("metrics", {}).get("iterations"),
                "diff_lines": result.get("metrics", {}).get("diff_lines"),
                "checks": checks,
                "summary": result.get("summary"),
                "verification": result.get("verification"),
            },
        })
    write_reports(results)
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0


def write_reports(results: List[Dict[str, Any]]) -> None:
    out_dir = Path("docs") / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    json_path = out_dir / f"v2-benchmark-{today}.json"
    md_path = out_dir / f"v2-benchmark-{today}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CodexSaver v2 Benchmark",
        "",
        f"Date: {today}",
        "",
        "Method: Codex-only is a normalized counterfactual baseline with cost index 1.00. "
        "CodexSaver results are real bounded work-packet runs through the configured worker provider.",
        "",
        "| Task | Kind | Codex-only cost | CodexSaver status | CodexSaver cost | Savings | Effect | Latency |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for item in results:
        cs = item["codexsaver"]
        lines.append(
            f"| {item['name']} | {item['kind']} | {item['codex_only']['cost_index']:.2f} | "
            f"{cs['status']} ({cs['execution_mode']}) | {cs['cost_index']:.2f} | {cs['estimated_savings_percent']}% | "
            f"{cs['effect_score']:.1f} | {cs['latency_seconds']:.2f}s |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
