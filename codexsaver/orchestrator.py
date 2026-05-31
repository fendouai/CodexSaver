from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import difflib
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .agent_registry import AgentCard, AgentRegistry
from .agent_router import AgentRouter
from .aggregator import PatchAggregator
from .context import ContextPacker
from .cost import CostEstimator
from .provider import ProviderClient, ProviderError
from .schema import (
    FileContext,
    OrchestrateTaskInput,
    SpecialistRunInput,
    WorkPacketInput,
    WorkGraphNode,
    to_dict,
)
from .pi_agent import PiAgentClient
from .specialists import SpecialistRegistry
from .task_lifecycle import TaskLifecycle, task_record_payload
from .work_graph import WorkGraphPlanner
from .work_packet import PatchSandbox, WorkPacketRuntime, changed_files_from_patch, verify_patch_policy


class V3Orchestrator:
    def __init__(self, registry: SpecialistRegistry | None = None,
                 agent_registry: AgentRegistry | None = None,
                 agent_router: AgentRouter | None = None):
        self.registry = registry or SpecialistRegistry()
        self.agent_registry = agent_registry or AgentRegistry()
        self.agent_router = agent_router or AgentRouter()
        self.task_lifecycle = TaskLifecycle()
        self.planner = WorkGraphPlanner(self.registry)
        self.aggregator = PatchAggregator()
        self.cost = CostEstimator()

    def orchestrate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request = OrchestrateTaskInput(
            goal=input_data["goal"],
            files=input_data.get("files", []),
            constraints=input_data.get("constraints", []),
            workspace=input_data.get("workspace", "."),
            max_parallel_workers=int(input_data.get("max_parallel_workers", 4)),
            dry_run=bool(input_data.get("dry_run", False)),
        )
        graph = self.planner.plan(request)
        preview = {
            "graph_id": graph.graph_id,
            "route": graph.route,
            "summary": graph.summary,
            "nodes": [to_dict(node) for node in graph.nodes],
            "blocked_actions": graph.blocked_actions,
            "codex_next_actions": graph.codex_next_actions,
            "handoff_summary": graph.handoff_summary,
        }
        agent_cards = self.agent_registry.discover(request.workspace)
        agent_routing = self._agent_routing_preview(agent_cards, graph.nodes)
        preview["agents"] = {
            "registry": "agent_card",
            "discovered": [self._agent_card_preview(card) for card in agent_cards],
            "routing": agent_routing,
        }

        if request.dry_run:
            return {
                "route": graph.route,
                "status": "dry_run",
                "summary": graph.summary,
                "graph": preview,
                "metrics": {
                    "node_count": len(graph.nodes),
                    "parallelizable_nodes": len([n for n in graph.nodes if n.mode != "readonly"]),
                    "estimated_savings_percent": self._estimate_savings(len(graph.nodes)),
                    "worker_participation_percent": self._participation_percent(0, len(graph.nodes), len(graph.blocked_actions)),
                    "discovered_agents": len(agent_cards),
                },
                "blocked_actions": graph.blocked_actions,
                "codex_next_actions": graph.codex_next_actions,
                "handoff_summary": graph.handoff_summary,
                "next_step": "Review the work graph, then execute safe worker nodes or keep blocked actions in Codex.",
            }

        return self._execute_graph(request, graph.nodes, preview)

    def specialist_preview(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request = SpecialistRunInput(
            specialist=input_data["specialist"],
            goal=input_data["goal"],
            files=input_data.get("files", []),
            allowed_files=input_data.get("allowed_files", []),
            forbidden_paths=input_data.get("forbidden_paths", []),
            acceptance_criteria=input_data.get("acceptance_criteria", []),
            allowed_commands=input_data.get("allowed_commands", []),
            workspace=input_data.get("workspace", "."),
            dry_run=bool(input_data.get("dry_run", False)),
        )
        profile = self.registry.get(request.specialist)
        node = WorkGraphNode(
            id=f"{request.specialist}-preview",
            type="bounded_patch" if profile.mode != "readonly" else "explain",
            goal=request.goal,
            depends_on=[],
            specialist=request.specialist,
            allowed_files=request.allowed_files,
            forbidden_paths=request.forbidden_paths,
            allowed_commands=request.allowed_commands,
            acceptance_criteria=request.acceptance_criteria,
            mode=profile.mode,
        )
        return {
            "route": "single_worker",
            "status": "dry_run" if request.dry_run else "planned",
            "specialist": to_dict(profile),
            "node_preview": to_dict(node),
        }

    def run_specialist(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request = SpecialistRunInput(
            specialist=input_data["specialist"],
            goal=input_data["goal"],
            files=input_data.get("files", []),
            allowed_files=input_data.get("allowed_files", []),
            forbidden_paths=input_data.get("forbidden_paths", []),
            acceptance_criteria=input_data.get("acceptance_criteria", []),
            allowed_commands=input_data.get("allowed_commands", []),
            workspace=input_data.get("workspace", "."),
            dry_run=bool(input_data.get("dry_run", False)),
        )
        preview = self.specialist_preview(input_data)
        if request.dry_run:
            return preview
        profile = self.registry.get(request.specialist)
        node = WorkGraphNode(
            id=f"{request.specialist}-run",
            type="bounded_patch" if profile.mode != "readonly" else "explain",
            goal=request.goal,
            depends_on=[],
            specialist=request.specialist,
            allowed_files=request.allowed_files,
            forbidden_paths=request.forbidden_paths,
            allowed_commands=request.allowed_commands,
            acceptance_criteria=request.acceptance_criteria,
            mode=profile.mode,
        )
        if profile.mode == "readonly":
            context = ContextPacker(workspace=request.workspace).load(request.files or request.allowed_files)
            result = self._run_readonly_node(node, context, request.workspace)
            result["route"] = "pi_agent" if result["status"] == "success" else "codex"
            return result
        return self._run_patch_node(node, request.workspace, request.files or request.allowed_files)

    def _execute_graph(self, request: OrchestrateTaskInput, nodes: List[WorkGraphNode],
                       preview: Dict[str, Any]) -> Dict[str, Any]:
        original_workspace = Path(request.workspace).resolve()
        current_workspace = self._copy_workspace(original_workspace)
        pending = {node.id: node for node in nodes}
        completed: set[str] = set()
        readonly_results: List[Dict[str, Any]] = []
        patch_results: List[Dict[str, Any]] = []

        while pending:
            ready = [
                node for node in pending.values()
                if all(dep in completed for dep in node.depends_on)
            ]
            if not ready:
                return self._needs_codex(
                    "Work graph dependencies could not be resolved.",
                    preview,
                    readonly_results + patch_results,
                    len(nodes),
                )

            readonly_ready = [node for node in ready if node.mode == "readonly"]
            patch_ready = [node for node in ready if node.mode != "readonly"]

            if readonly_ready:
                batch = self._execute_readonly_batch(current_workspace, request.files, readonly_ready, request.max_parallel_workers)
                readonly_results.extend(batch)
                if any(item["status"] != "success" for item in batch):
                    return self._needs_codex(
                        "One or more readonly specialists failed; Codex should take over.",
                        preview,
                        readonly_results + patch_results,
                        len(nodes),
                    )
                for node in readonly_ready:
                    completed.add(node.id)
                    pending.pop(node.id, None)

            if patch_ready:
                batch = self._execute_patch_batch(current_workspace, request.files, patch_ready, request.max_parallel_workers)
                if batch["status"] != "success":
                    return self._needs_codex(
                        batch["summary"],
                        preview,
                        readonly_results + patch_results + batch.get("results", []),
                        len(nodes),
                    )
                patch_results.extend(batch["results"])
                for node in patch_ready:
                    completed.add(node.id)
                    pending.pop(node.id, None)

        aggregate = self._build_final_aggregate_patch(original_workspace, current_workspace, patch_results)
        return {
            "route": "pi_agent",
            "status": "success",
            "summary": "v3 graph executed successfully.",
            "graph": preview,
            "results": readonly_results + patch_results,
            "aggregate_patch": aggregate["patch"],
            "changed_files": aggregate["changed_files"],
            "checks": [check for item in patch_results for check in item.get("checks", [])],
            "verification": {
                "ok": True,
                "fallback_to_codex": False,
                "reason": "All v3 nodes completed and aggregated successfully.",
                "warnings": [],
                "executed_commands": [check for item in patch_results for check in item.get("checks", [])],
            },
            "metrics": {
                "node_count": len(nodes),
                "readonly_nodes": len(readonly_results),
                "patch_nodes": len(patch_results),
                "worker_calls": len(readonly_results) + len(patch_results),
                "repair_count": self._repair_count(readonly_results + patch_results),
                "estimated_savings_percent": self._estimate_savings(len(nodes)),
                "worker_participation_percent": self._participation_percent(
                    len(readonly_results) + len(patch_results),
                    len(nodes),
                    len(preview.get("blocked_actions", [])),
                ),
            },
            "codex_review_notes": aggregate["notes"],
            "handoff": self._handoff_payload(
                status="success",
                summary="All worker nodes completed. Codex should review and apply if safe.",
                results=readonly_results + patch_results,
                blocked_actions=preview.get("blocked_actions", []),
                codex_next_actions=preview.get("codex_next_actions", []),
            ),
            "blocked_actions": preview.get("blocked_actions", []),
            "codex_next_actions": preview.get("codex_next_actions", []),
            "next_step": "Review the aggregate patch and specialist findings before applying changes.",
        }

    def _execute_readonly_batch(self, workspace: Path, base_files: List[str],
                                nodes: List[WorkGraphNode], max_parallel_workers: int) -> List[Dict[str, Any]]:
        context_files = base_files or [path for node in nodes for path in node.allowed_files]
        context = ContextPacker(workspace=str(workspace)).load(context_files)
        max_workers = min(max(1, max_parallel_workers), max(1, len(nodes)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(lambda node: self._run_readonly_node(node, context, str(workspace)), nodes))

    def _execute_patch_batch(self, workspace: Path, base_files: List[str],
                             nodes: List[WorkGraphNode], max_parallel_workers: int) -> Dict[str, Any]:
        max_workers = min(max(1, max_parallel_workers), max(1, len(nodes)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(
                lambda node: self._run_patch_node(node, str(workspace), base_files),
                nodes,
            ))
        results = self._repair_failed_patch_nodes(workspace, base_files, nodes, results)
        failed = [item for item in results if item["status"] != "success"]
        lint_rounds = 0
        lint = self._lint_patch_results(workspace, nodes, results)
        while lint_rounds < 2 and lint.get("repairable"):
            results = self._repair_lint_failed_patch_nodes(workspace, base_files, nodes, results, lint)
            failed = [item for item in results if item["status"] != "success"]
            if failed:
                break
            lint_rounds += 1
            lint = self._lint_patch_results(workspace, nodes, results)
        if failed:
            return {
                "status": "needs_codex",
                "summary": "One or more patch specialists failed verification.",
                "results": results,
            }
        if not lint["ok"]:
            return {
                "status": "needs_codex",
                "summary": f"Patch lint failed before aggregation: {lint['reason']}",
                "results": results,
                "lint": lint,
            }
        aggregate = self.aggregator.aggregate(results)
        if not aggregate.ok:
            return {
                "status": "needs_codex",
                "summary": "Patch aggregation found overlapping file writes.",
                "results": results,
            }
        try:
            self._apply_results_to_workspace(workspace, results)
        except RuntimeError as e:
            return {
                "status": "needs_codex",
                "summary": f"Patch aggregation could not be materialized safely: {e}",
                "results": results,
            }
        return {
            "status": "success",
            "results": results,
        }

    def _repair_failed_patch_nodes(self, workspace: Path, base_files: List[str],
                                   nodes: List[WorkGraphNode],
                                   results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        repaired: List[Dict[str, Any]] = []
        node_by_id = {node.id: node for node in nodes}
        for result in results:
            if result.get("status") == "success":
                repaired.append(result)
                continue
            node = node_by_id.get(str(result.get("node_id")))
            if node is None:
                repaired.append(result)
                continue
            repair_node = WorkGraphNode(
                id=node.id,
                type=node.type,
                goal=(
                    f"{node.goal}\n\nRepair the previous failed patch node. "
                    f"Failure summary: {result.get('summary', '')}. "
                    f"Risk notes: {result.get('risk_notes', [])}. "
                    "Return a complete corrected patch with verification_plan and rollback_notes."
                ),
                depends_on=node.depends_on,
                specialist=node.specialist,
                allowed_files=node.allowed_files,
                forbidden_paths=node.forbidden_paths,
                allowed_commands=node.allowed_commands,
                acceptance_criteria=node.acceptance_criteria,
                mode=node.mode,
                action_type=node.action_type,
                risk_domain=node.risk_domain,
                execution_policy=node.execution_policy,
            )
            repair_result = self._run_patch_node(repair_node, str(workspace), base_files, force_repair=True)
            if repair_result.get("status") == "success":
                repair_result["repair_of"] = result
                repaired.append(repair_result)
            else:
                result["repair_attempt"] = repair_result
                repaired.append(result)
        return repaired

    def _repair_lint_failed_patch_nodes(self, workspace: Path, base_files: List[str],
                                        nodes: List[WorkGraphNode],
                                        results: List[Dict[str, Any]],
                                        lint: Dict[str, Any]) -> List[Dict[str, Any]]:
        node_id = str(lint.get("node_id") or "")
        if not node_id:
            return results
        node_by_id = {node.id: node for node in nodes}
        node = node_by_id.get(node_id)
        if node is None:
            return results
        replacement_index = next(
            (index for index, item in enumerate(results) if str(item.get("node_id")) == node_id),
            -1,
        )
        if replacement_index < 0:
            return results
        prior_result = results[replacement_index]
        repair_node = WorkGraphNode(
            id=node.id,
            type=node.type,
            goal=(
                f"{node.goal}\n\nRepair the previous patch after a patch-lint failure. "
                f"Lint issue type: {lint.get('issue_type', 'unknown')}. "
                f"Lint failure: {lint.get('reason', '')}. "
                f"Previous summary: {prior_result.get('summary', '')}. "
                "Return a corrected patch with exact changed_files, verification_plan, and rollback_notes."
            ),
            depends_on=node.depends_on,
            specialist=node.specialist,
            allowed_files=node.allowed_files,
            forbidden_paths=node.forbidden_paths,
            allowed_commands=node.allowed_commands,
            acceptance_criteria=node.acceptance_criteria,
            mode=node.mode,
            action_type=node.action_type,
            risk_domain=node.risk_domain,
            execution_policy=node.execution_policy,
        )
        repair_result = self._run_patch_node(repair_node, str(workspace), base_files, force_repair=True)
        if repair_result.get("status") != "success":
            prior_result["lint_repair_attempt"] = repair_result
            return results
        repair_result["lint_repair_of"] = prior_result
        updated = list(results)
        updated[replacement_index] = repair_result
        return updated

    def _lint_patch_results(self, workspace: Path, nodes: List[WorkGraphNode],
                            results: List[Dict[str, Any]]) -> Dict[str, Any]:
        node_by_id = {node.id: node for node in nodes}
        seen: set[str] = set()
        for item in results:
            patch = str(item.get("patch", ""))
            if item.get("preflight_satisfied"):
                continue
            if not patch.strip():
                return self._lint_failure(
                    item,
                    "empty_patch",
                    f"Empty patch from {item.get('specialist')}",
                )
            patch_files = changed_files_from_patch(patch)
            declared_files = sorted(set(item.get("changed_files", [])))
            if sorted(patch_files) != declared_files:
                return self._lint_failure(
                    item,
                    "changed_files_mismatch",
                    (
                        f"changed_files mismatch for {item.get('specialist')}: "
                        f"declared={declared_files}, patch={patch_files}"
                    ),
                )
            duplicate = [path for path in patch_files if path in seen]
            if duplicate:
                return self._lint_failure(
                    item,
                    "duplicate_changed_files",
                    f"Duplicate changed_files before aggregation: {duplicate}",
                    repairable=False,
                )
            seen.update(patch_files)
            node = node_by_id.get(str(item.get("node_id")))
            allowed_files = node.allowed_files if node else declared_files
            forbidden_paths = node.forbidden_paths if node else []
            packet = WorkPacketInput(
                goal=str(item.get("summary", "")),
                files=[],
                constraints=[],
                acceptance_criteria=[],
                allowed_files=allowed_files,
                forbidden_paths=forbidden_paths,
                allowed_commands=[],
                workspace=str(workspace),
            )
            policy = verify_patch_policy(patch, packet)
            if not policy.ok:
                return self._lint_failure(
                    item,
                    "patch_policy",
                    policy.reason,
                    warnings=policy.warnings,
                )
            sandbox = PatchSandbox(workspace, packet)
            observation = sandbox.propose_patch(patch)
            if observation.get("type") != "patch_applied":
                return self._lint_failure(
                    item,
                    "patch_apply",
                    observation.get("reason", "Patch did not apply."),
                    observation=observation,
                )
            if not item.get("verification_plan"):
                return self._lint_failure(
                    item,
                    "missing_verification_plan",
                    f"Missing verification_plan for {item.get('specialist')}",
                )
            if not item.get("rollback_notes"):
                return self._lint_failure(
                    item,
                    "missing_rollback_notes",
                    f"Missing rollback_notes for {item.get('specialist')}",
                )
            metadata_issue = self._validate_patch_result_metadata(item, node, patch_files)
            if metadata_issue:
                return metadata_issue
        return {"ok": True, "reason": "Patch lint passed."}

    def _validate_patch_result_metadata(self, item: Dict[str, Any], node: WorkGraphNode | None,
                                        patch_files: List[str]) -> Dict[str, Any] | None:
        if node is None or node.specialist != "test_writer":
            return None
        python_test_files = [path for path in patch_files if _is_python_test_file(path)]
        if not python_test_files:
            return self._lint_failure(
                item,
                "test_writer_missing_test_file",
                "test_writer must change at least one Python test file under tests/test_*.py.",
            )
        verification_plan = [str(entry) for entry in item.get("verification_plan", [])]
        pytest_entries = [entry for entry in verification_plan if "pytest" in entry]
        if not pytest_entries:
            return self._lint_failure(
                item,
                "test_writer_missing_pytest",
                "test_writer verification_plan must include an exact pytest command.",
            )
        missing_commands = [
            path for path in python_test_files
            if not any(path in entry for entry in pytest_entries)
        ]
        if missing_commands:
            return self._lint_failure(
                item,
                "test_writer_pytest_path_mismatch",
                f"test_writer verification_plan must mention the generated test file: {missing_commands}",
            )
        rollback_text = " ".join(str(entry) for entry in item.get("rollback_notes", [])).lower()
        if not any(word in rollback_text for word in ["delete", "revert", "remove"]):
            return self._lint_failure(
                item,
                "test_writer_rollback_too_vague",
                "test_writer rollback_notes must explain how to delete or revert the generated test file.",
            )
        return None

    def _lint_failure(self, item: Dict[str, Any], issue_type: str, reason: str,
                      repairable: bool = True, **extra: Any) -> Dict[str, Any]:
        payload = {
            "ok": False,
            "issue_type": issue_type,
            "reason": reason,
            "node_id": item.get("node_id"),
            "specialist": item.get("specialist"),
            "repairable": repairable,
        }
        payload.update(extra)
        return payload

    def _execute_readonly_graph(self, request: OrchestrateTaskInput,
                                nodes: List[WorkGraphNode]) -> Dict[str, Any]:
        context = ContextPacker(workspace=request.workspace).load(request.files)
        max_workers = min(max(1, request.max_parallel_workers), max(1, len(nodes)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(lambda node: self._run_readonly_node(node, context, request.workspace), nodes))

        failed = [item for item in results if item["status"] != "success"]
        if failed:
            return {
                "route": "codex",
                "status": "needs_codex",
                "summary": "One or more readonly specialists failed; Codex should take over.",
                "results": results,
                "metrics": {
                    "node_count": len(nodes),
                    "worker_calls": len(results),
                    "estimated_savings_percent": 0,
                },
                "next_step": "Review the failing specialist result and continue in Codex.",
            }

        specialist_summaries = [
            f"{item['specialist']}: {item['summary']}" for item in results
        ]
        review_notes = []
        for item in results:
            review_notes.extend(item.get("risk_notes", []))
        return {
            "route": "pi_agent",
            "status": "success",
            "summary": "Readonly specialists completed in parallel.",
            "results": results,
            "aggregate_patch": "",
            "changed_files": [],
            "checks": [],
            "verification": {
                "ok": True,
                "fallback_to_codex": False,
                "reason": "Readonly specialists completed without patch generation.",
                "warnings": [],
                "executed_commands": [],
            },
            "metrics": {
                "node_count": len(nodes),
                "worker_calls": len(results),
                "estimated_savings_percent": self._estimate_savings(len(nodes)),
                "worker_participation_percent": self._participation_percent(len(results), len(nodes), 0),
            },
            "codex_review_notes": review_notes,
            "combined_summary": specialist_summaries,
            "handoff": self._handoff_payload(
                status="success",
                summary="Readonly specialists completed. Codex can use these findings for the next step.",
                results=results,
                blocked_actions=[],
                codex_next_actions=["Review readonly findings and decide whether bounded patch execution is appropriate."],
            ),
            "next_step": "Review the readonly findings and decide whether to continue with bounded patch execution.",
        }

    def _run_readonly_node(self, node: WorkGraphNode, context: List[FileContext],
                           workspace: str = ".") -> Dict[str, Any]:
        profile = self.registry.get(node.specialist)
        selected = self._select_agent(node, workspace)
        worker_id = selected.get("worker", {}).get("id", "unknown")
        task = self.task_lifecycle.running(self.task_lifecycle.submitted(node.id, worker_id))
        try:
            client = self._client_for_node(profile.provider, profile.model, selected)
            response = client.complete_json(
                _readonly_system_prompt(profile.name),
                {
                    "specialist": profile.name,
                    "goal": node.goal,
                    "acceptance_criteria": node.acceptance_criteria,
                    "context": [to_dict(item) for item in context],
                },
            )
        except ProviderError as e:
            task = self.task_lifecycle.failed(task)
            return {
                "node_id": node.id,
                "specialist": profile.name,
                "status": "failed",
                "summary": f"{profile.name} failed: {e}",
                "findings": [],
                "risk_notes": [str(e)],
                "selected_worker": selected,
                "task_lifecycle": task_record_payload(task),
            }
        task = self.task_lifecycle.completed(task) if response.get("status") == "success" else self.task_lifecycle.failed(task)
        return {
            "node_id": node.id,
            "specialist": profile.name,
            "status": response.get("status", "failed"),
            "summary": str(response.get("summary", "")),
            "findings": list(response.get("findings", [])),
            "risk_notes": list(response.get("risk_notes", [])),
            "worker_usage": response.get("_worker_usage", {}),
            "worker_provider": response.get("_worker_provider", ""),
            "worker_model": response.get("_worker_model", ""),
            "selected_worker": selected,
            "task_lifecycle": task_record_payload(task),
        }

    def _run_patch_node(self, node: WorkGraphNode, workspace: str,
                        base_files: List[str], force_repair: bool = False) -> Dict[str, Any]:
        profile = self.registry.get(node.specialist)
        context_files = list(dict.fromkeys((base_files or []) + node.allowed_files))
        selected = self._select_agent(node, workspace)
        worker_id = selected.get("worker", {}).get("id", "unknown")
        task = self.task_lifecycle.running(self.task_lifecycle.submitted(node.id, worker_id))
        try:
            runtime = WorkPacketRuntime(self._client_for_node(profile.provider, profile.model, selected))
            result = runtime.run(WorkPacketInput(
                goal=node.goal,
                files=context_files,
                constraints=_specialist_constraints(profile.name),
                acceptance_criteria=node.acceptance_criteria,
                allowed_files=node.allowed_files,
                forbidden_paths=node.forbidden_paths,
                allowed_commands=node.allowed_commands,
                workspace=workspace,
                delegation_level="repair_loop" if (node.allowed_commands or force_repair) else "bounded_impl",
                max_iterations=4 if force_repair else 3,
                max_diff_lines=300,
            ))
        except (ProviderError, ValueError) as e:
            task = self.task_lifecycle.failed(task)
            return {
                "node_id": node.id,
                "specialist": profile.name,
                "status": "failed",
                "summary": f"{profile.name} failed: {e}",
                "changed_files": [],
                "patch": "",
                "checks": [],
                "risk_notes": [str(e)],
                "selected_worker": selected,
                "task_lifecycle": task_record_payload(task),
            }
        task = self.task_lifecycle.completed(task) if result.get("status") == "success" else self.task_lifecycle.failed(task)
        result["node_id"] = node.id
        result["specialist"] = profile.name
        result["selected_worker"] = selected
        result["task_lifecycle"] = task_record_payload(task)
        return result

    def _select_agent(self, node: WorkGraphNode, workspace: str = ".") -> Dict[str, Any]:
        cards = self.agent_registry.discover(workspace)
        return self.agent_router.select(node, cards)

    def _client_for_node(self, provider: str, model: str, selected: Dict[str, Any]):
        if provider == "pi-agent":
            worker = selected.get("worker")
            if not worker:
                raise ProviderError("No Pi Agent worker selected for this node.")
            return PiAgentClient(AgentCard(**worker))
        return ProviderClient(provider=provider, model=model)

    def _agent_routing_preview(self, cards, nodes: List[WorkGraphNode]) -> Dict[str, Any]:
        return {
            node.id: self.agent_router.select(node, cards)
            for node in nodes
        }

    def _agent_card_preview(self, card) -> Dict[str, Any]:
        return {
            "id": card.id,
            "name": card.name,
            "type": card.type,
            "status": card.status,
            "capabilities": card.capabilities,
            "languages": card.languages,
            "endpoint": card.endpoint,
            "command": card.command,
            "cost_weight": card.cost_weight,
            "success_rate": card.success_rate,
            "current_load": card.current_load,
            "context_window": card.context_window,
            "worktree_path": card.worktree_path,
            "permissions_config": card.permissions_config,
            "filesystem_policy": card.filesystem_policy,
            "network_policy": card.network_policy,
            "source": card.source,
        }

    def _copy_workspace(self, workspace: Path) -> Path:
        target = Path(tempfile.mkdtemp(prefix="codexsaver-v3-"))
        shutil.copytree(
            workspace,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git", ".omx", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache", "node_modules", "*.pyc", "*.pyo",
            ),
        )
        return target

    def _apply_results_to_workspace(self, workspace: Path, results: List[Dict[str, Any]]) -> None:
        for item in results:
            self._materialize_patch_effects(str(workspace), item)

    def _materialize_patch_effects(self, workspace: str, result: Dict[str, Any]) -> None:
        packet = WorkPacketInput(
            goal=result.get("summary", ""),
            files=[],
            constraints=[],
            acceptance_criteria=[],
            allowed_files=result.get("changed_files", []),
            forbidden_paths=[],
            allowed_commands=[],
            workspace=workspace,
        )
        from .work_packet import PatchSandbox  # local import to avoid expanding public surface

        patch_sandbox = PatchSandbox(Path(workspace).resolve(), packet)
        observation = patch_sandbox.propose_patch(str(result.get("patch", "")))
        if observation["type"] != "patch_applied" or patch_sandbox.tempdir is None:
            raise RuntimeError(f"Failed to apply node patch to aggregate workspace: {result.get('specialist')}")
        workspace_path = Path(workspace)
        shutil.rmtree(workspace_path)
        shutil.copytree(patch_sandbox.tempdir, workspace_path, dirs_exist_ok=True)

    def _build_final_aggregate_patch(self, original_workspace: Path, current_workspace: Path,
                                     patch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        changed_files = list(dict.fromkeys(
            path for item in patch_results for path in item.get("changed_files", [])
        ))
        patches: List[str] = []
        notes: List[str] = []
        for rel in changed_files:
            original = original_workspace / rel
            current = current_workspace / rel
            old_text = original.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if original.exists() else []
            new_text = current.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if current.exists() else []
            diff = "".join(difflib.unified_diff(
                old_text,
                new_text,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            ))
            if diff:
                patches.append(diff)
        if not patches:
            notes.append("No aggregate patch was produced after executing patch nodes.")
        return {
            "patch": "".join(patches).strip(),
            "changed_files": changed_files,
            "notes": notes,
        }

    def _needs_codex(self, summary: str, preview: Dict[str, Any], results: List[Dict[str, Any]],
                     node_count: int) -> Dict[str, Any]:
        completed_worker_results = [
            item for item in results
            if item.get("status") == "success"
        ]
        return {
            "route": "codex",
            "status": "needs_codex",
            "summary": summary,
            "graph": preview,
            "results": results,
            "metrics": {
                "node_count": node_count,
                "worker_calls": len(results),
                "repair_count": self._repair_count(results),
                "estimated_savings_percent": 0,
                "worker_participation_percent": self._participation_percent(
                    len(completed_worker_results),
                    node_count,
                    len(preview.get("blocked_actions", [])),
                ),
            },
            "handoff": self._handoff_payload(
                status="partial" if completed_worker_results else "needs_codex",
                summary=summary,
                results=results,
                blocked_actions=preview.get("blocked_actions", []),
                codex_next_actions=preview.get("codex_next_actions", []),
            ),
            "blocked_actions": preview.get("blocked_actions", []),
            "codex_next_actions": preview.get("codex_next_actions", []),
            "partial_delegation": bool(completed_worker_results),
            "next_step": "Review partial specialist output and continue in Codex.",
        }

    def _estimate_savings(self, node_count: int) -> int:
        if node_count <= 1:
            return 45
        if node_count == 2:
            return 52
        return 58

    def _participation_percent(self, worker_completed: int, worker_planned: int,
                               codex_blocked_actions: int = 0) -> int:
        total = max(1, worker_planned + codex_blocked_actions)
        return round(worker_completed * 100 / total)

    def _repair_count(self, results: List[Dict[str, Any]]) -> int:
        return sum(
            1 for item in results
            if item.get("repair_of") or item.get("lint_repair_of")
        )

    def _handoff_payload(self, status: str, summary: str, results: List[Dict[str, Any]],
                         blocked_actions: List[str], codex_next_actions: List[str]) -> Dict[str, Any]:
        delegated_work_done = [
            {
                "node_id": item.get("node_id"),
                "specialist": item.get("specialist"),
                "status": item.get("status"),
                "summary": item.get("summary"),
                "changed_files": item.get("changed_files", []),
                "findings": item.get("findings", []),
                "risk_notes": item.get("risk_notes", []),
            }
            for item in results
        ]
        commands_to_run = [
            command
            for item in results
            for command in item.get("commands_to_run", [])
        ]
        return {
            "status": status,
            "summary": summary,
            "delegated_work_done": delegated_work_done,
            "commands_to_run": commands_to_run,
            "blocked_actions": blocked_actions,
            "codex_next_actions": codex_next_actions or [
                "Review delegated evidence.",
                "Run verification commands where appropriate.",
                "Keep high-risk execution in Codex.",
            ],
        }


def _readonly_system_prompt(specialist_name: str) -> str:
    if specialist_name == "perf_reviewer":
        role = "You are CodexSaver's readonly performance reviewer."
    else:
        role = "You are CodexSaver's readonly code explainer."
    return (
        f"{role}\n\n"
        "Return valid JSON only. No markdown fences.\n"
        "Do not propose patches.\n"
        "Do not claim changes were made.\n"
        "Keep output concise and specific to the provided files.\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "status": "success | needs_codex | failed",\n'
        '  "summary": "short summary",\n'
        '  "findings": ["short note"],\n'
        '  "risk_notes": ["short note"]\n'
        "}\n"
    )


def _specialist_constraints(specialist_name: str) -> List[str]:
    if specialist_name == "test_writer":
        return [
            "Generate or update focused tests only.",
            "Prefer pytest for Python and Jest-style structure for JS/TS.",
            "Cover normal path, edge cases, and one failure path when practical.",
            "Before writing tests, infer the exact import path from the target file path.",
            "Put Python tests under tests/test_<module>.py unless an existing test file is allowlisted.",
            "verification_plan must include the exact pytest command for the generated test file.",
            "rollback_notes must explain that deleting the generated test file reverts the change.",
        ]
    if specialist_name == "doc_writer":
        return [
            "Add concise inline docs, docstrings, or README text only.",
            "Do not change runtime behavior unless documentation must match an existing implementation.",
        ]
    if specialist_name == "impl_worker":
        return [
            "Implement only the bounded requested behavior.",
            "Prefer minimal reviewable changes and avoid unrelated refactors.",
        ]
    return []


def _is_python_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("tests/test_") and normalized.endswith(".py")
