from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .context import ContextPacker
from .cost import CostEstimator
from .config import load_compression_config, resolve_provider_config
from .provider import ProviderClient, ProviderError
from .router import PROTECTED_PATH_KEYWORDS, Router
from .schema import DelegateTaskInput, WorkPacketInput, WorkerTask, to_dict
from .orchestrator import V3Orchestrator
from .verifier import Verifier
from .work_packet import WorkPacketRuntime


DEFAULT_CONSTRAINTS = [
    "Return JSON only.",
    "Prefer minimal, reviewable changes.",
    "Do not claim tests passed unless test output is provided.",
    "If uncertain or risky, return status=needs_codex.",
]


class CodexSaverEngine:
    def __init__(self):
        self.router = Router()
        self.verifier = Verifier()
        self.cost = CostEstimator()
        self.orchestrator = V3Orchestrator()

    def delegate_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        provider = resolve_provider_config()
        compression = load_compression_config()
        req = DelegateTaskInput(
            instruction=input_data["instruction"],
            files=input_data.get("files", []),
            constraints=input_data.get("constraints", []),
            workspace=input_data.get("workspace", "."),
            max_files=int(input_data.get("max_files", 8)),
            max_chars_per_file=int(input_data.get("max_chars_per_file", 24_000)),
            max_total_chars=int(input_data.get("max_total_chars", 120_000)),
            dry_run=bool(input_data.get("dry_run", False)),
        )

        decision = self.router.decide(req.instruction, req.files)

        packer = ContextPacker(
            max_files=req.max_files,
            max_chars_per_file=req.max_chars_per_file,
            max_total_chars=req.max_total_chars,
            workspace=req.workspace,
        )

        task = WorkerTask(
            instruction=req.instruction,
            task_type=decision.task_type,
            risk=decision.risk,
            constraints=(req.constraints or []) + DEFAULT_CONSTRAINTS,
            workspace=str(Path(req.workspace).resolve()),
            files=packer.load(req.files),
        )

        if decision.route == "codex":
            return {
                "route": "codex", "status": "needs_codex",
                "decision": to_dict(decision), "estimated_savings_percent": 0,
                "message": "CodexSaver recommends Codex handle this task directly.",
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="codex",
                    status="needs_codex",
                    estimated_savings_percent=0,
                    mode="codex_takeover",
                    detail="Protected domain or ambiguous task detected before delegation.",
                    compression=compression,
                ),
            }

        estimated_savings = self.cost.estimate_savings_percent(task, delegated=True)

        if req.dry_run:
            return {
                "route": "deepseek", "status": "dry_run",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "estimated_savings_percent": estimated_savings,
                "task_preview": to_dict(task),
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="deepseek",
                    status="dry_run",
                    estimated_savings_percent=estimated_savings,
                    mode="preview",
                    detail="Dry-run preview only. No external model call was made.",
                    compression=compression,
                ),
            }

        try:
            worker = ProviderClient(provider=provider.name)
            worker_result = worker.complete_task(task)
        except ProviderError as e:
            return {
                "route": "codex", "status": "failed",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "estimated_savings_percent": 0,
                "message": f"Worker provider failed; Codex should take over. Error: {e}",
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="codex",
                    status="failed",
                    estimated_savings_percent=0,
                    mode="codex_takeover",
                    detail=f"Delegation failed and control returned to Codex: {e}",
                    compression=compression,
                ),
            }

        verification = self.verifier.verify(worker_result, decision, workspace=task.workspace)

        final_route = "deepseek" if not verification.fallback_to_codex else "codex"
        final_status = "success" if verification.ok else "needs_codex"
        final_savings = estimated_savings if verification.ok else 0

        return {
            "route": final_route,
            "status": final_status,
            "decision": to_dict(decision),
            "provider": _provider_payload(provider),
            "estimated_savings_percent": final_savings,
            "verification": to_dict(verification),
            "result": worker_result,
            "codex_instruction": (
                "Review the patch carefully. Apply only if safe. "
                "Run or ask the user to run commands_to_run before finalizing."
            ),
            "compression": {
                "enabled": compression["enabled"],
                "level": compression["level"],
            },
            "interaction": self._interaction_payload(
                decision=to_dict(decision),
                route=final_route,
                status=final_status,
                estimated_savings_percent=final_savings,
                mode="delegated_execution" if verification.ok else "codex_takeover",
                detail=verification.reason,
                compression=compression,
            ),
        }

    def _interaction_payload(self, decision: Dict[str, Any], route: str, status: str,
                             estimated_savings_percent: int, mode: str,
                             detail: str,
                             compression: Dict[str, Any] | None = None) -> Dict[str, Any]:
        task_type = decision["task_type"]
        risk = decision["risk"]
        tool_name = "codexsaver.delegate_task"
        if route == "deepseek" and status == "success":
            headline = "CodexSaver delegated this task to the configured worker provider."
            next_step = "Review the worker result and apply it only if the patch looks safe."
        elif route == "deepseek" and status == "dry_run":
            headline = "CodexSaver previewed a delegated run."
            next_step = "Call the tool without dry_run to execute the delegated task."
        elif status == "failed":
            headline = "CodexSaver attempted delegation but returned control to Codex."
            next_step = "Handle the task in Codex or retry after fixing the worker/API issue."
        else:
            headline = "CodexSaver kept this task in Codex."
            next_step = "Use Codex directly because the task is risky, protected, or ambiguous."
        payload = {
            "tool": tool_name,
            "mode": mode,
            "headline": headline,
            "route_label": f"[CodexSaver] route={route} task_type={task_type} risk={risk}",
            "reason": decision["reason"],
            "detail": detail,
            "estimated_savings_percent": estimated_savings_percent,
            "next_step": next_step,
        }
        if compression and compression.get("enabled"):
            payload["compression"] = {
                "enabled": True,
                "level": compression.get("level", "full"),
                "note": f"Worker output compression enabled at level={compression.get('level', 'full')}",
            }
        return payload

    def delegate_work_packet(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        provider = resolve_provider_config()
        compression = load_compression_config()
        goal = input_data["goal"]
        files = input_data.get("files", [])
        decision = self.router.decide(goal, files)
        if decision.route == "codex" and input_data.get("delegation_level") not in {"research"}:
            return {
                "route": "codex",
                "status": "needs_codex",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "message": "CodexSaver recommends Codex handle this work packet directly.",
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="codex",
                    status="needs_codex",
                    estimated_savings_percent=0,
                    mode="codex_takeover",
                    detail="Protected domain or ambiguous work packet detected before delegation.",
                    compression=compression,
                ),
            }

        packet = WorkPacketInput(
            goal=goal,
            files=files,
            constraints=input_data.get("constraints", []),
            acceptance_criteria=input_data.get("acceptance_criteria", []),
            allowed_files=input_data.get("allowed_files") or files,
            forbidden_paths=input_data.get("forbidden_paths") or DEFAULT_FORBIDDEN_PATHS,
            allowed_commands=input_data.get("allowed_commands", []),
            workspace=input_data.get("workspace", "."),
            delegation_level=input_data.get("delegation_level", "bounded_impl"),
            max_iterations=int(input_data.get("max_iterations", 3)),
            max_diff_lines=int(input_data.get("max_diff_lines", 300)),
            max_files=int(input_data.get("max_files", 8)),
            max_chars_per_file=int(input_data.get("max_chars_per_file", 24_000)),
            max_total_chars=int(input_data.get("max_total_chars", 120_000)),
            dry_run=bool(input_data.get("dry_run", False)),
        )

        if packet.delegation_level != "research" and not packet.allowed_files:
            return {
                "route": "codex",
                "status": "needs_codex",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "message": "delegate_work_packet requires allowed_files for write-capable delegation.",
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="codex",
                    status="needs_codex",
                    estimated_savings_percent=0,
                    mode="codex_takeover",
                    detail="No allowed_files were provided for a write-capable work packet.",
                    compression=compression,
                ),
            }

        estimate_task = WorkerTask(
            instruction=packet.goal,
            task_type=decision.task_type,
            risk=decision.risk,
            constraints=packet.constraints,
            workspace=str(Path(packet.workspace).resolve()),
            files=[],
        )
        estimated_savings = self.cost.estimate_savings_percent(estimate_task, delegated=True)

        if packet.dry_run:
            return {
                "route": "deepseek",
                "status": "dry_run",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "estimated_savings_percent": estimated_savings,
                "work_packet_preview": to_dict(packet),
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="deepseek",
                    status="dry_run",
                    estimated_savings_percent=estimated_savings,
                    mode="preview",
                    detail="Dry-run work packet preview only. No external model call was made.",
                    compression=compression,
                ),
            }

        try:
            runtime = WorkPacketRuntime(ProviderClient(provider=provider.name))
            worker_result = runtime.run(packet)
        except (ProviderError, ValueError) as e:
            return {
                "route": "codex",
                "status": "failed",
                "decision": to_dict(decision),
                "provider": _provider_payload(provider),
                "estimated_savings_percent": 0,
                "message": f"Worker runtime failed; Codex should take over. Error: {e}",
                "interaction": self._interaction_payload(
                    decision=to_dict(decision),
                    route="codex",
                    status="failed",
                    estimated_savings_percent=0,
                    mode="codex_takeover",
                    detail=f"Delegation failed and control returned to Codex: {e}",
                    compression=compression,
                ),
            }

        worker_result["decision"] = to_dict(decision)
        worker_result["provider"] = _provider_payload(provider)
        worker_result["estimated_savings_percent"] = (
            100 if worker_result.get("preflight_satisfied")
            else estimated_savings if worker_result["status"] == "success"
            else 0
        )
        worker_result["codex_instruction"] = (
            "Review the sandboxed patch and evidence. Apply only if the diff is safe."
        )
        worker_result["interaction"] = self._interaction_payload(
            decision=to_dict(decision),
            route=worker_result["route"],
            status=worker_result["status"],
            estimated_savings_percent=worker_result["estimated_savings_percent"],
            mode="bounded_implementation" if worker_result["status"] == "success" else "codex_takeover",
            detail=worker_result["verification"]["reason"],
            compression=compression,
        )
        return worker_result

    def orchestrate_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.orchestrator.orchestrate(input_data)

    def run_specialist(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.orchestrator.run_specialist(input_data)


DEFAULT_FORBIDDEN_PATHS = [
    ".github/**",
    "deploy/**",
    "infra/**",
    "terraform/**",
    ".env*",
    "*secret*",
    *[f"*{keyword}*" for keyword in PROTECTED_PATH_KEYWORDS],
]


def _provider_payload(provider) -> Dict[str, Any]:
    return {
        "name": provider.name,
        "model": provider.model,
        "model_source": provider.model_source,
        "base_url": provider.base_url,
        "base_url_source": provider.base_url_source,
        "api_style": provider.api_style,
        "requires_api_key": provider.requires_api_key,
        "api_key_configured": bool(provider.api_key),
        "api_key_source": provider.api_key_source,
    }
