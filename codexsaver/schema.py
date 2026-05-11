from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Literal

RiskLevel = Literal["low", "medium", "high"]
Route = Literal["codex", "deepseek"]
TaskType = Literal[
    "code_search",
    "explain",
    "write_tests",
    "fix_lint",
    "docs",
    "boilerplate",
    "simple_refactor",
    "review_draft",
    "unknown",
]
DelegationLevel = Literal["research", "draft_patch", "bounded_impl", "repair_loop"]


@dataclass
class FileContext:
    path: str
    content: str


@dataclass
class DelegateTaskInput:
    instruction: str
    files: List[str]
    constraints: List[str]
    workspace: str = "."
    max_files: int = 8
    max_chars_per_file: int = 24_000
    max_total_chars: int = 120_000
    dry_run: bool = False


@dataclass
class RouteDecision:
    route: Route
    task_type: TaskType
    risk: RiskLevel
    reason: str
    protected_hits: List[str]


@dataclass
class WorkerTask:
    instruction: str
    task_type: TaskType
    risk: RiskLevel
    constraints: List[str]
    workspace: str
    files: List[FileContext]


@dataclass
class WorkPacketInput:
    goal: str
    files: List[str]
    constraints: List[str]
    acceptance_criteria: List[str]
    allowed_files: List[str]
    forbidden_paths: List[str]
    allowed_commands: List[str]
    workspace: str = "."
    delegation_level: DelegationLevel = "bounded_impl"
    max_iterations: int = 3
    max_diff_lines: int = 300
    max_files: int = 8
    max_chars_per_file: int = 24_000
    max_total_chars: int = 120_000
    dry_run: bool = False


@dataclass
class WorkerAction:
    action: str
    args: Dict[str, Any]


@dataclass
class WorkPacketVerification:
    ok: bool
    fallback_to_codex: bool
    reason: str
    warnings: List[str]
    executed_commands: List[Dict[str, Any]]
    changed_files: List[str]
    diff_lines: int


@dataclass
class VerificationResult:
    ok: bool
    fallback_to_codex: bool
    reason: str
    warnings: List[str]
    executed_commands: List[Dict[str, Any]]


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)
