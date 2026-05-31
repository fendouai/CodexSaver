from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from cli import main
from codexsaver.aggregator import PatchAggregator
from codexsaver.engine import CodexSaverEngine
from codexsaver.provider import ProviderError
from codexsaver.schema import WorkGraph, WorkGraphNode
from codexsaver.specialists import SpecialistRegistry
from codexsaver.work_graph import WorkGraphPlanner


def test_specialist_registry_lists_defaults():
    registry = SpecialistRegistry()
    names = [item.name for item in registry.list()]
    assert "doc_writer" in names
    assert "explainer" in names
    assert "impl_worker" in names
    assert "test_writer" in names


def test_work_graph_planner_builds_multi_worker_graph():
    planner = WorkGraphPlanner()
    graph = planner.plan(type("Req", (), {
        "goal": "Implement config parser, add tests, add docs, and explain risk",
        "files": ["src/config_parser.py"],
        "constraints": [],
        "workspace": ".",
        "max_parallel_workers": 4,
        "dry_run": True,
    })())
    assert graph.route == "multi_worker"
    assert len(graph.nodes) >= 3
    assert any(node.specialist == "test_writer" for node in graph.nodes)
    assert any(node.specialist == "doc_writer" for node in graph.nodes)
    test_nodes = [node for node in graph.nodes if node.specialist == "test_writer"]
    assert test_nodes[0].allowed_commands == ["python -m pytest tests/test_config_parser.py -q"]


def test_patch_aggregator_detects_conflicts():
    result = PatchAggregator().aggregate([
        {"changed_files": ["README.md"], "patch": "diff1"},
        {"changed_files": ["README.md"], "patch": "diff2"},
    ])
    assert result.ok is False
    assert result.conflicts == ["README.md"]


def test_engine_orchestrate_task_dry_run():
    result = CodexSaverEngine().orchestrate_task({
        "goal": "Implement config parser, add tests, and add docs",
        "files": ["src/config_parser.py"],
        "dry_run": True,
    })
    assert result["status"] == "dry_run"
    assert result["route"] == "multi_worker"
    assert result["graph"]["nodes"]


def test_engine_orchestrate_task_executes_readonly_specialists_in_parallel():
    with patch("codexsaver.orchestrator.PiAgentClient") as MockClient:
        client = MockClient.return_value
        client.complete_json.side_effect = [
            {
                "status": "success",
                "summary": "Code path explained.",
                "findings": ["Main branch calls parse_config first."],
                "risk_notes": [],
            },
            {
                "status": "success",
                "summary": "Performance review completed.",
                "findings": ["Loop may become O(n^2) on large inputs."],
                "risk_notes": ["Consider caching repeated lookups."],
            },
        ]
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Explain config loader logic and review performance",
            "files": ["codexsaver/config.py"],
        })

    assert result["status"] == "success"
    assert result["route"] == "pi_agent"
    assert result["aggregate_patch"] == ""
    assert len(result["results"]) == 2
    assert result["results"][0]["status"] == "success"
    assert result["results"][1]["status"] == "success"
    assert result["metrics"]["worker_calls"] == 2


def test_engine_orchestrate_task_readonly_failure_returns_codex():
    with patch("codexsaver.orchestrator.PiAgentClient") as MockClient:
        client = MockClient.return_value
        client.complete_json.side_effect = ProviderError("timeout")
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Explain config loader logic",
            "files": ["codexsaver/config.py"],
        })

    assert result["status"] == "needs_codex"
    assert result["route"] == "codex"
    assert result["results"][0]["status"] == "failed"


def test_engine_orchestrate_task_executes_patch_nodes_and_aggregates(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "config_parser.py").write_text("pass\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.V3Orchestrator._apply_results_to_workspace"), \
            patch("codexsaver.orchestrator.V3Orchestrator._build_final_aggregate_patch", return_value={
                "patch": "aggregate",
                "changed_files": ["src/config_parser.py", "tests/test_config_parser.py"],
                "notes": [],
            }):
        runtime = MockRuntime.return_value
        runtime.run.side_effect = [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "implemented login",
                "changed_files": ["src/config_parser.py"],
                "patch": (
                    "--- a/src/config_parser.py\n"
                    "+++ b/src/config_parser.py\n"
                    "@@ -1 +1,2 @@\n"
                    "-pass\n"
                    "+pass\n"
                    "+return True\n"
                ),
                "checks": [],
                "verification_plan": ["python -m pytest tests/test_config_parser.py -q"],
                "rollback_notes": ["Revert src/config_parser.py."],
                "risk_notes": [],
            },
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
                    "+def test_login(): pass\n"
                ),
                "checks": [{"command": "pytest tests/test_config_parser.py -q", "exit_code": 0}],
                "verification_plan": ["python -m pytest tests/test_config_parser.py -q"],
                "rollback_notes": ["Delete tests/test_config_parser.py."],
                "risk_notes": [],
            },
        ]
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Implement config parser and add tests",
            "files": ["src/config_parser.py"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "success"
    assert result["route"] == "pi_agent"
    assert "src/config_parser.py" in result["changed_files"]
    assert "tests/test_config_parser.py" in result["changed_files"]
    assert result["metrics"]["patch_nodes"] == 2


def test_engine_orchestrate_task_patch_conflict_returns_codex(tmp_path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.V3Orchestrator._apply_results_to_workspace"), \
            patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=WorkGraph(
                graph_id="graph-conflict",
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
            )):
        runtime = MockRuntime.return_value
        runtime.run.side_effect = [
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
        ]
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Add docs and update README docs",
            "files": ["README.md"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "needs_codex"
    assert result["route"] == "codex"


def test_engine_orchestrate_repairs_failed_patch_node(tmp_path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=WorkGraph(
                graph_id="graph-repair",
                route="single_worker",
                summary="repair graph",
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
            )):
        runtime = MockRuntime.return_value
        runtime.run.side_effect = [
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
        ]
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Update README docs",
            "files": ["README.md"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "success"
    assert result["results"][0]["repair_of"]["status"] == "needs_codex"


def test_engine_orchestrate_lints_missing_verification_plan(tmp_path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=WorkGraph(
                graph_id="graph-lint",
                route="single_worker",
                summary="lint graph",
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
            )):
        runtime = MockRuntime.return_value
        runtime.run.return_value = {
            "route": "pi_agent",
            "status": "success",
            "summary": "doc patch",
            "changed_files": ["README.md"],
            "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
            "checks": [],
            "risk_notes": [],
        }
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Update README docs",
            "files": ["README.md"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "needs_codex"
    assert "verification_plan" in result["summary"]


def test_engine_orchestrate_repairs_lint_failed_changed_files_mismatch(tmp_path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=WorkGraph(
                graph_id="graph-lint-repair",
                route="single_worker",
                summary="lint repair graph",
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
            )):
        runtime = MockRuntime.return_value
        runtime.run.side_effect = [
            {
                "route": "pi_agent",
                "status": "success",
                "summary": "doc patch with bad metadata",
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
                "summary": "repaired doc patch",
                "changed_files": ["README.md"],
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                "checks": [],
                "verification_plan": ["Review README.md."],
                "rollback_notes": ["Revert README.md."],
                "risk_notes": [],
            },
        ]
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Update README docs",
            "files": ["README.md"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "success"
    assert result["results"][0]["lint_repair_of"]["changed_files"] == ["NOT_README.md"]
    assert result["metrics"]["repair_count"] == 1


def test_engine_orchestrate_lints_test_writer_missing_exact_pytest_command(tmp_path):
    target_dir = tmp_path / "tests"
    target_dir.mkdir()
    with patch("codexsaver.orchestrator.PiAgentClient"), \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.WorkGraphPlanner.plan", return_value=WorkGraph(
                graph_id="graph-test-writer-lint",
                route="single_worker",
                summary="test writer lint graph",
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
            )):
        runtime = MockRuntime.return_value
        runtime.run.return_value = {
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
        }
        result = CodexSaverEngine().orchestrate_task({
            "goal": "Add config parser tests",
            "files": ["tests/test_config_parser.py"],
            "workspace": str(tmp_path),
        })

    assert result["status"] == "needs_codex"
    assert "generated test file" in result["summary"]


def test_work_graph_planner_splits_database_write_into_safe_prep_nodes():
    planner = WorkGraphPlanner()
    graph = planner.plan(type("Req", (), {
        "goal": "Rebuild database schema and write imported OCR text into lessons",
        "files": ["scripts/import_textbooks.py"],
        "constraints": [],
        "workspace": ".",
        "max_parallel_workers": 4,
        "dry_run": True,
    })())
    assert graph.blocked_actions
    assert graph.codex_next_actions
    assert len(graph.nodes) >= 2
    assert any(node.mode == "readonly" for node in graph.nodes)
    assert any(node.execution_policy == "dry_run_only" for node in graph.nodes)


def test_engine_orchestrate_task_reports_partial_handoff_for_blocked_database_write():
    with patch("codexsaver.orchestrator.PiAgentClient") as MockClient, \
            patch("codexsaver.orchestrator.WorkPacketRuntime") as MockRuntime, \
            patch("codexsaver.orchestrator.V3Orchestrator._apply_results_to_workspace"), \
            patch("codexsaver.orchestrator.V3Orchestrator._build_final_aggregate_patch", return_value={
                "patch": "aggregate",
                "changed_files": ["docs/codexsaver-dry-run-import_textbooks.md"],
                "notes": [],
            }):
        client = MockClient.return_value
        client.complete_json.return_value = {
            "status": "success",
            "summary": "Readonly database flow inspected.",
            "findings": ["Importer should default to dry-run."],
            "risk_notes": ["Actual --apply must stay in Codex."],
        }
        runtime = MockRuntime.return_value
        runtime.run.return_value = {
            "route": "pi_agent",
            "status": "success",
            "summary": "created dry-run validation notes",
            "changed_files": ["docs/codexsaver-dry-run-import_textbooks.md"],
            "patch": "--- a/docs/codexsaver-dry-run-import_textbooks.md\n+++ b/docs/codexsaver-dry-run-import_textbooks.md\n@@ -0,0 +1 @@\n+dry run only\n",
            "checks": [],
            "verification_plan": ["Review dry-run documentation."],
            "rollback_notes": ["Delete docs/codexsaver-dry-run-import_textbooks.md."],
            "risk_notes": ["No writes executed."],
        }

        result = CodexSaverEngine().orchestrate_task({
            "goal": "Rebuild database schema and write imported OCR text into lessons",
            "files": ["scripts/import_textbooks.py"],
            "workspace": ".",
        })

    assert result["status"] == "success"
    assert result["blocked_actions"]
    assert result["handoff"]["blocked_actions"]
    assert result["metrics"]["worker_participation_percent"] >= 50


def test_engine_run_specialist_preview():
    result = CodexSaverEngine().run_specialist({
        "specialist": "test_writer",
        "goal": "Add tests for parse_config",
        "allowed_files": ["tests/test_config.py"],
        "dry_run": True,
    })
    assert result["status"] == "dry_run"
    assert result["specialist"]["name"] == "test_writer"
    assert result["node_preview"]["specialist"] == "test_writer"


def test_engine_run_specialist_executes_readonly(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text("def f():\n    return 1\n", encoding="utf-8")
    with patch("codexsaver.orchestrator.PiAgentClient") as MockClient:
        client = MockClient.return_value
        client.complete_json.return_value = {
            "status": "success",
            "summary": "Function explained.",
            "findings": ["Returns a constant integer."],
            "risk_notes": [],
        }
        result = CodexSaverEngine().run_specialist({
            "specialist": "explainer",
            "goal": "Explain this function",
            "files": [str(sample)],
            "workspace": str(tmp_path),
        })

    assert result["route"] == "pi_agent"
    assert result["status"] == "success"
    assert result["summary"] == "Function explained."


def test_cli_orchestrate_dry_run(capsys):
    assert main([
        "orchestrate",
        "Implement config parser, add tests, and add docs",
        "--files",
        "src/config_parser.py",
        "--dry-run",
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "dry_run"
    assert output["graph"]["route"] == "multi_worker"
