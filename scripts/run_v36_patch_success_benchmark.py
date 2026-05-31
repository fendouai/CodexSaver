#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

from codexsaver.engine import CodexSaverEngine
from codexsaver.schema import WorkGraph, WorkGraphNode


ROOT = Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()
OUT_JSON = ROOT / "docs" / "benchmarks" / f"v36-patch-success-benchmark-{TODAY}.json"
OUT_MD = ROOT / "docs" / "benchmarks" / f"v36-patch-success-benchmark-{TODAY}.md"


SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "node_repair_success",
        "name": "Node repair after initial patch failure",
        "goal": "Update README docs",
        "files": ["README.md"],
        "seed_files": {"README.md": "old\n"},
        "graph": WorkGraph(
            graph_id="bench-node-repair",
            route="single_worker",
            summary="single doc patch",
            nodes=[
                WorkGraphNode(
                    id="docs-1",
                    type="bounded_patch",
                    goal="update readme",
                    depends_on=[],
                    specialist="doc_writer",
                    allowed_files=["README.md"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
            ],
        ),
        "runtime_outputs": [
            {
                "route": "codex",
                "status": "needs_codex",
                "summary": "first patch failed",
                "changed_files": [],
                "patch": "",
                "checks": [],
                "risk_notes": ["Patch did not apply."],
            },
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "repaired doc patch",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
        ],
        "expected_current_status": "success",
        "expected_current_verified": True,
        "baseline": {
            "status": "success",
            "verified_success": True,
            "reason": "Old v3.5 already retried patch nodes that failed before lint.",
        },
    },
    {
        "id": "lint_changed_files_repair",
        "name": "Lint repair for changed_files mismatch",
        "goal": "Update README docs",
        "files": ["README.md"],
        "seed_files": {"README.md": "old\n"},
        "graph": WorkGraph(
            graph_id="bench-lint-changed-files",
            route="single_worker",
            summary="lint repair",
            nodes=[
                WorkGraphNode(
                    id="docs-1",
                    type="bounded_patch",
                    goal="update readme",
                    depends_on=[],
                    specialist="doc_writer",
                    allowed_files=["README.md"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
            ],
        ),
        "runtime_outputs": [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "bad metadata",
                "changed_files": ["NOT_README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "repaired metadata",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
        ],
        "expected_current_status": "success",
        "expected_current_verified": True,
        "baseline": {
            "status": "needs_codex",
            "verified_success": False,
            "reason": "Old v3.5 failed patch lint and returned to Codex without a lint-repair round.",
        },
    },
    {
        "id": "lint_missing_verification_plan_repair",
        "name": "Lint repair for missing verification plan",
        "goal": "Update README docs",
        "files": ["README.md"],
        "seed_files": {"README.md": "old\n"},
        "graph": WorkGraph(
            graph_id="bench-lint-missing-verification",
            route="single_worker",
            summary="lint repair",
            nodes=[
                WorkGraphNode(
                    id="docs-1",
                    type="bounded_patch",
                    goal="update readme",
                    depends_on=[],
                    specialist="doc_writer",
                    allowed_files=["README.md"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
            ],
        ),
        "runtime_outputs": [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "doc patch missing verification plan",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "risk_notes": [],
            },
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "repaired doc patch",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
        ],
        "expected_current_status": "success",
        "expected_current_verified": True,
        "baseline": {
            "status": "needs_codex",
            "verified_success": False,
            "reason": "Old v3.5 rejected missing verification_plan and stopped there.",
        },
    },
    {
        "id": "test_writer_pytest_path_repair",
        "name": "test_writer exact pytest path repair",
        "goal": "Add config parser tests",
        "files": ["tests/test_config_parser.py"],
        "seed_files": {"tests/.keep": ""},
        "graph": WorkGraph(
            graph_id="bench-test-writer",
            route="single_worker",
            summary="test writer repair",
            nodes=[
                WorkGraphNode(
                    id="tests-1",
                    type="bounded_patch",
                    goal="add parser tests",
                    depends_on=[],
                    specialist="test_writer",
                    allowed_files=["tests/test_config_parser.py"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
            ],
        ),
        "runtime_outputs": [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "added tests",
                "changed_files": ["tests/test_config_parser.py"],
                "patch": (
                    "diff --git a/tests/test_config_parser.py b/tests/test_config_parser.py\n"
                    "new file mode 100644\n"
                    "--- /dev/null\n"
                    "+++ b/tests/test_config_parser.py\n"
                    "@@ -0,0 +1 @@\n"
                    "+def test_config_parser():\n"
                ),
                "checks": [],
                "verification_plan": ["python -m pytest -q"],
                "rollback_notes": ["Delete tests/test_config_parser.py."],
                "risk_notes": [],
            },
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "added tests with exact command",
                "changed_files": ["tests/test_config_parser.py"],
                "patch": (
                    "diff --git a/tests/test_config_parser.py b/tests/test_config_parser.py\n"
                    "new file mode 100644\n"
                    "--- /dev/null\n"
                    "+++ b/tests/test_config_parser.py\n"
                    "@@ -0,0 +1 @@\n"
                    "+def test_config_parser():\n"
                ),
                "checks": [],
                "verification_plan": ["python -m pytest tests/test_config_parser.py -q"],
                "rollback_notes": ["Delete tests/test_config_parser.py to revert the test."],
                "risk_notes": [],
            },
        ],
        "expected_current_status": "success",
        "expected_current_verified": True,
        "baseline": {
            "status": "success",
            "verified_success": False,
            "reason": "Old v3.5 accepted any non-empty verification_plan and could silently pass a weak pytest command.",
        },
    },
    {
        "id": "duplicate_changed_files_blocked",
        "name": "Duplicate file writes remain blocked",
        "goal": "Add docs and update README docs",
        "files": ["README.md"],
        "seed_files": {"README.md": "old\n"},
        "graph": WorkGraph(
            graph_id="bench-duplicate-conflict",
            route="multi_worker",
            summary="conflict graph",
            nodes=[
                WorkGraphNode(
                    id="docs-1",
                    type="bounded_patch",
                    goal="update readme first",
                    depends_on=[],
                    specialist="doc_writer",
                    allowed_files=["README.md"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
                WorkGraphNode(
                    id="docs-2",
                    type="bounded_patch",
                    goal="update readme second",
                    depends_on=[],
                    specialist="doc_writer",
                    allowed_files=["README.md"],
                    forbidden_paths=[],
                    allowed_commands=[],
                    acceptance_criteria=[],
                    mode="bounded_patch",
                ),
            ],
        ),
        "runtime_outputs": [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "doc patch",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+first\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "another doc patch",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+second\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
        ],
        "expected_current_status": "needs_codex",
        "expected_current_verified": False,
        "baseline": {
            "status": "needs_codex",
            "verified_success": False,
            "reason": "Duplicate file writes should remain blocked; this is a safety guard, not a repair target.",
        },
    },
]


def main() -> int:
    results = [run_scenario(scenario) for scenario in SCENARIOS]
    payload = {
        "version": "0.3.6",
        "date": TODAY,
        "benchmark": "v36-patch-success",
        "workspace": str(ROOT),
        "method": (
            "Deterministic patch benchmark. Each scenario replays fixed worker outputs against the current "
            "orchestrator and compares them with a simulated pre-fix v3.5 baseline. "
            "This isolates orchestration robustness rather than live model variance."
        ),
        "summary": summarize(results),
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "json": str(OUT_JSON),
        "markdown": str(OUT_MD),
        "summary": payload["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


def run_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="codexsaver-v36-patch-bench-") as tmpdir:
        workspace = Path(tmpdir) / "repo"
        copy_workspace(ROOT, workspace)
        seed_workspace(workspace, scenario.get("seed_files", {}))
        started = time.perf_counter()
        with patch("codexsaver.orchestrator.PiAgentClient"), \
                patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
                patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=deepcopy(scenario["graph"])):
            runtime = MockRuntime.return_value
            runtime.run.side_effect = deepcopy(scenario["runtime_outputs"])
            result = CodexSaverEngine().orchestrate_task({
                "goal": scenario["goal"],
                "files": scenario["files"],
                "workspace": str(workspace),
            })
        elapsed = time.perf_counter() - started
    current_verified = verify_current_result(scenario["id"], result)
    baseline = scenario["baseline"]
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "current": {
            "status": result.get("status"),
            "summary": result.get("summary"),
            "verified_success": current_verified,
            "repair_count": result.get("metrics", {}).get("repair_count", 0),
            "worker_calls": result.get("metrics", {}).get("worker_calls", 0),
            "latency_seconds": round(elapsed, 3),
        },
        "baseline": baseline,
        "delta": {
            "status_changed": baseline["status"] != result.get("status"),
            "verified_outcome_gain": int(current_verified) - int(bool(baseline["verified_success"])),
        },
    }


def copy_workspace(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            ".git", ".omx", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
            "node_modules", "*.pyc", "*.pyo",
        ),
    )


def seed_workspace(workspace: Path, files: Dict[str, str]) -> None:
    for rel, content in files.items():
        path = workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def verify_current_result(scenario_id: str, result: Dict[str, Any]) -> bool:
    if scenario_id == "duplicate_changed_files_blocked":
        return result.get("status") == "needs_codex"
    if result.get("status") != "success":
        return False
    results = result.get("results", [])
    if scenario_id == "test_writer_pytest_path_repair":
        if not results:
            return False
        item = results[0]
        plans = item.get("verification_plan", [])
        return any("tests/test_config_parser.py" in entry and "pytest" in entry for entry in plans)
    return True


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    baseline_verified = sum(1 for item in results if item["baseline"]["verified_success"])
    current_verified = sum(1 for item in results if item["current"]["verified_success"])
    baseline_write_success = sum(1 for item in results if item["baseline"]["status"] == "success")
    current_success = sum(1 for item in results if item["current"]["status"] == "success")
    return {
        "scenarios": len(results),
        "baseline_write_successes": baseline_write_success,
        "current_write_successes": current_success,
        "baseline_write_success_rate": round(baseline_write_success / max(1, len(results)), 2),
        "current_write_success_rate": round(current_success / max(1, len(results)), 2),
        "baseline_verified_outcomes": baseline_verified,
        "current_verified_outcomes": current_verified,
        "baseline_verified_outcome_rate": round(baseline_verified / max(1, len(results)), 2),
        "current_verified_outcome_rate": round(current_verified / max(1, len(results)), 2),
        "verified_outcome_gain": current_verified - baseline_verified,
        "average_repair_count": round(
            sum(item["current"]["repair_count"] for item in results) / max(1, len(results)),
            2,
        ),
        "average_latency_seconds": round(
            sum(item["current"]["latency_seconds"] for item in results) / max(1, len(results)),
            3,
        ),
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        f"# CodexSaver v3.6 Patch Success Benchmark — {payload['date']}",
        "",
        payload["method"],
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend([
        "",
        "## Results",
        "",
        "| Scenario | Baseline status | Baseline verified outcome | Current status | Current verified outcome | Repair count | Delta |",
        "|---|---|---:|---|---:|---:|---:|",
    ])
    for item in payload["results"]:
        lines.append(
            f"| {item['name']} | `{item['baseline']['status']}` | "
            f"{int(bool(item['baseline']['verified_success']))} | `{item['current']['status']}` | "
            f"{int(bool(item['current']['verified_success']))} | {item['current']['repair_count']} | "
            f"{item['delta']['verified_outcome_gain']:+d} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `write_success_rate` measures how many scenarios ended in a successful worker-produced patch.",
        "- `verified_outcome_rate` is broader: it also counts scenarios where CodexSaver correctly preserved a safety block instead of producing an unsafe patch.",
        "- The largest gain comes from lint-repair: fixable metadata and verification mistakes no longer force an immediate return to Codex.",
        "- `test_writer` is now stricter: weak pytest plans do not count as verified success unless the exact generated test file is covered.",
        "- Duplicate writes remain blocked on purpose. This benchmark treats that as preserved safety, not lost capability.",
        "- The benchmark is deterministic and isolates orchestrator behavior, so it should be used alongside live Pi Agent benchmarks rather than instead of them.",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
