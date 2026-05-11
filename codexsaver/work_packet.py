from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .context import ContextPacker
from .provider import ProviderClient
from .router import PROTECTED_PATH_KEYWORDS
from .schema import FileContext, WorkPacketInput, WorkPacketVerification, to_dict


WORKER_PACKET_PROMPT = """
You are CodexSaver's bounded coding worker.

Codex owns the final decision. You implement only inside the work packet.

Return exactly one JSON object, no markdown fences.

Allowed actions:
- search_code: {"pattern": "text or regex", "path": "optional relative path"}
- open_file: {"path": "relative path", "line": 1, "limit": 120}
- list_files: {"glob": "*.py"}
- propose_patch: {"patch": "unified diff"}
- run_check: {"command_id": 0}
- finish: {"summary": "...", "patch": "...", "changed_files": ["..."], "risk_notes": ["..."]}
- escalate: {"reason": "..."}

Rules:
- Do not edit files directly.
- Do not request arbitrary shell commands.
- Only propose unified diffs.
- Keep patches small and within allowed_files.
- Run allowed checks when useful.
- For draft_patch, bounded_impl, and repair_loop, do not finish without a non-empty patch.
- If allowed_commands is non-empty, run at least one allowed check before finish.
- If blocked, risky, or ambiguous, use escalate.
""".strip()


WORKER_PATCH_PROMPT = """
You are CodexSaver's bounded implementation worker.

Codex owns the final decision. You implement only the work packet.

Return valid JSON only. No markdown fences.

Required JSON shape:
{
  "status": "success | needs_codex | failed",
  "summary": "short summary",
  "changed_files": ["relative/path"],
  "patch": "unified diff",
  "risk_notes": ["short note"]
}

Rules:
- Produce a non-empty unified diff when status="success".
- Touch only allowed_files.
- Do not touch forbidden_paths.
- Keep the patch within max_diff_lines.
- If the previous observation contains a patch/check failure, repair the patch.
- If you cannot safely complete the work packet, return status="needs_codex".

Unified diff example for creating a new file:
diff --git a/docs/example.md b/docs/example.md
new file mode 100644
--- /dev/null
+++ b/docs/example.md
@@ -0,0 +1 @@
+hello
""".strip()


IGNORED_DIRS = {
    ".git",
    ".omx",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}


SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,})",
    re.IGNORECASE,
)


class WorkPacketRuntime:
    def __init__(self, provider: ProviderClient | None = None):
        self.provider = provider or ProviderClient()

    def run(self, packet: WorkPacketInput) -> Dict[str, Any]:
        workspace = Path(packet.workspace).resolve()
        packer = ContextPacker(
            max_files=packet.max_files,
            max_chars_per_file=packet.max_chars_per_file,
            max_total_chars=packet.max_total_chars,
            workspace=str(workspace),
        )
        context = packer.load(packet.files)
        sandbox = PatchSandbox(workspace, packet)
        if packet.delegation_level in {"draft_patch", "bounded_impl", "repair_loop"}:
            preflight = sandbox.preflight_checks()
            if preflight["type"] == "already_satisfied":
                verification = WorkPacketVerification(
                    ok=True,
                    fallback_to_codex=False,
                    reason="Work packet already satisfied before delegation.",
                    warnings=[],
                    executed_commands=preflight["results"],
                    changed_files=[],
                    diff_lines=0,
                )
                return work_packet_result(
                    packet,
                    [{"role": "environment", "observation": preflight}],
                    verification,
                    {
                        "summary": "Work packet already satisfied before delegation.",
                        "patch": "",
                        "changed_files": [],
                        "risk_notes": [],
                        "preflight_satisfied": True,
                    },
                )
            return self._run_patch_loop(packet, context, sandbox)
        transcript: List[Dict[str, Any]] = []
        observation: Dict[str, Any] = {
            "type": "start",
            "work_packet": packet_payload(packet, context),
        }

        for iteration in range(max(1, packet.max_iterations)):
            action = self.provider.complete_json(WORKER_PACKET_PROMPT, {
                "iteration": iteration + 1,
                "max_iterations": packet.max_iterations,
                "transcript": transcript[-8:],
                "observation": observation,
            })
            normalized = normalize_action(action)
            transcript.append({"role": "worker", "action": normalized})
            observation = self._execute_action(normalized, workspace, packet, sandbox)
            transcript.append({"role": "environment", "observation": observation})

            if observation["type"] == "finished":
                verification = sandbox.finalize(observation["result"])
                return work_packet_result(packet, transcript, verification, observation["result"])
            if observation["type"] == "escalated":
                verification = WorkPacketVerification(
                    ok=False,
                    fallback_to_codex=True,
                    reason=observation["reason"],
                    warnings=[],
                    executed_commands=[],
                    changed_files=[],
                    diff_lines=0,
                )
                return work_packet_result(packet, transcript, verification, {})

        verification = WorkPacketVerification(
            ok=False,
            fallback_to_codex=True,
            reason="Worker exceeded max_iterations.",
            warnings=[],
            executed_commands=sandbox.executed_commands,
            changed_files=[],
            diff_lines=0,
        )
        return work_packet_result(packet, transcript, verification, {})

    def _run_patch_loop(self, packet: WorkPacketInput, context: List[FileContext],
                        sandbox: "PatchSandbox") -> Dict[str, Any]:
        transcript: List[Dict[str, Any]] = []
        observation: Dict[str, Any] = {
            "type": "start",
            "message": "Create a complete unified diff for this work packet.",
        }
        for iteration in range(max(1, packet.max_iterations)):
            worker_result = self.provider.complete_json(WORKER_PATCH_PROMPT, {
                "iteration": iteration + 1,
                "max_iterations": packet.max_iterations,
                "work_packet": packet_payload(packet, context),
                "previous_observation": observation,
            })
            transcript.append({"role": "worker", "result": worker_result})
            status = worker_result.get("status")
            if status != "success":
                verification = WorkPacketVerification(
                    ok=False,
                    fallback_to_codex=True,
                    reason=f"Worker returned status={status}.",
                    warnings=[],
                    executed_commands=sandbox.executed_commands,
                    changed_files=[],
                    diff_lines=0,
                )
                return work_packet_result(packet, transcript, verification, worker_result)
            observation = sandbox.propose_patch(str(worker_result.get("patch", "")))
            transcript.append({"role": "environment", "observation": observation})
            if observation["type"] != "patch_applied":
                continue
            for command_id in range(len(packet.allowed_commands)):
                check_observation = sandbox.run_check(command_id)
                transcript.append({"role": "environment", "observation": check_observation})
                if check_observation["type"] != "check_result" or check_observation["result"]["exit_code"] != 0:
                    observation = check_observation
                    break
            verification = sandbox.finalize(worker_result)
            if verification.ok:
                return work_packet_result(packet, transcript, verification, worker_result)
            observation = {"type": "verification_failed", "verification": to_dict(verification)}
            transcript.append({"role": "environment", "observation": observation})

        verification = WorkPacketVerification(
            ok=False,
            fallback_to_codex=True,
            reason="Worker did not produce a verified patch within max_iterations.",
            warnings=[],
            executed_commands=sandbox.executed_commands,
            changed_files=changed_files_from_patch(sandbox.patch),
            diff_lines=count_diff_lines(sandbox.patch),
        )
        return work_packet_result(packet, transcript, verification, {})

    def _execute_action(self, action: Dict[str, Any], workspace: Path,
                        packet: WorkPacketInput, sandbox: "PatchSandbox") -> Dict[str, Any]:
        name = action["action"]
        args = action.get("args", {})
        if name == "search_code":
            if not args.get("pattern"):
                return {"type": "action_rejected", "reason": "search_code requires args.pattern."}
            return search_code(workspace, str(args.get("pattern", "")), str(args.get("path", ".")))
        if name == "open_file":
            if not args.get("path"):
                return {"type": "action_rejected", "reason": "open_file requires args.path."}
            return open_file(
                workspace,
                str(args.get("path", "")),
                int(args.get("line", 1) or 1),
                int(args.get("limit", 120) or 120),
            )
        if name == "list_files":
            return list_files(workspace, str(args.get("glob", "*")))
        if name == "propose_patch":
            return sandbox.propose_patch(str(args.get("patch", "")))
        if name == "run_check":
            return sandbox.run_check(int(args.get("command_id", 0) or 0))
        if name == "finish":
            patch = str(args.get("patch", sandbox.patch))
            if packet.delegation_level in {"draft_patch", "bounded_impl", "repair_loop"} and not patch.strip():
                return {
                    "type": "action_rejected",
                    "reason": "finish requires a non-empty patch for this delegation level.",
                }
            if packet.allowed_commands and not sandbox.executed_commands:
                return {
                    "type": "action_rejected",
                    "reason": "finish requires running an allowed check first.",
                }
            return {
                "type": "finished",
                "result": {
                    "status": "success",
                    "summary": str(args.get("summary", "")),
                    "patch": patch,
                    "changed_files": list(args.get("changed_files", [])),
                    "commands_to_run": packet.allowed_commands,
                    "risk_notes": list(args.get("risk_notes", [])),
                },
            }
        if name == "escalate":
            return {"type": "escalated", "reason": str(args.get("reason", "Worker escalated."))}
        return {"type": "error", "message": f"Unknown action: {name}"}


class PatchSandbox:
    def __init__(self, workspace: Path, packet: WorkPacketInput):
        self.workspace = workspace
        self.packet = packet
        self.tempdir: Path | None = None
        self.patch = ""
        self.executed_commands: List[Dict[str, Any]] = []

    def preflight_checks(self) -> Dict[str, Any]:
        if not self.packet.allowed_commands:
            return {"type": "preflight_skipped", "reason": "No allowed commands."}
        tempdir = self._fresh_workspace()
        results: List[Dict[str, Any]] = []
        for command in self.packet.allowed_commands:
            completed = subprocess.run(
                command,
                cwd=str(tempdir),
                shell=True,
                text=True,
                capture_output=True,
                timeout=120,
            )
            result = {
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
            results.append(result)
            if completed.returncode != 0:
                self.executed_commands = []
                self.tempdir = None
                return {"type": "preflight_failed", "results": results}
        self.executed_commands = results
        return {"type": "already_satisfied", "results": results}

    def propose_patch(self, patch: str) -> Dict[str, Any]:
        patch = normalize_patch(patch)
        if not patch.strip():
            return {"type": "patch_rejected", "reason": "Patch is empty."}
        quick = verify_patch_policy(patch, self.packet)
        if not quick.ok:
            return {"type": "patch_rejected", "reason": quick.reason, "warnings": quick.warnings}
        self.tempdir = self._fresh_workspace()
        completed = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=str(self.tempdir),
            input=patch,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            return {
                "type": "patch_rejected",
                "reason": "Patch did not apply cleanly.",
                "stderr": completed.stderr[-4000:],
            }
        self.patch = patch
        return {
            "type": "patch_applied",
            "changed_files": changed_files_from_patch(patch),
            "diff_lines": count_diff_lines(patch),
            "message": "Patch applied in sandbox.",
        }

    def run_check(self, command_id: int) -> Dict[str, Any]:
        if self.tempdir is None:
            return {"type": "check_rejected", "reason": "No patch has been applied in sandbox."}
        if command_id < 0 or command_id >= len(self.packet.allowed_commands):
            return {"type": "check_rejected", "reason": f"Unknown command_id: {command_id}"}
        command = self.packet.allowed_commands[command_id]
        completed = subprocess.run(
            command,
            cwd=str(self.tempdir),
            shell=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
        result = {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        self.executed_commands.append(result)
        return {"type": "check_result", "result": result}

    def finalize(self, result: Dict[str, Any]) -> WorkPacketVerification:
        patch = str(result.get("patch") or self.patch)
        policy = verify_patch_policy(patch, self.packet)
        if not policy.ok:
            return policy
        if self.packet.allowed_commands and not self.executed_commands:
            return WorkPacketVerification(
                ok=False,
                fallback_to_codex=True,
                reason="Required allowed checks were not run.",
                warnings=[],
                executed_commands=[],
                changed_files=changed_files_from_patch(patch),
                diff_lines=count_diff_lines(patch),
            )
        failed = [c for c in self.executed_commands if c["exit_code"] != 0]
        if failed:
            return WorkPacketVerification(
                ok=False,
                fallback_to_codex=True,
                reason=f"Allowed check failed: {failed[0]['command']}",
                warnings=[],
                executed_commands=self.executed_commands,
                changed_files=changed_files_from_patch(patch),
                diff_lines=count_diff_lines(patch),
            )
        return WorkPacketVerification(
            ok=True,
            fallback_to_codex=False,
            reason="Work packet passed sandbox verification.",
            warnings=policy.warnings,
            executed_commands=self.executed_commands,
            changed_files=changed_files_from_patch(patch),
            diff_lines=count_diff_lines(patch),
        )

    def _fresh_workspace(self) -> Path:
        if self.tempdir and self.tempdir.exists():
            shutil.rmtree(self.tempdir)
        tempdir = Path(tempfile.mkdtemp(prefix="codexsaver-work-"))
        shutil.copytree(
            self.workspace,
            tempdir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*IGNORED_DIRS, "*.pyc", "*.pyo"),
        )
        return tempdir


def normalize_action(action: Dict[str, Any]) -> Dict[str, Any]:
    name = action.get("action") or action.get("type")
    args = action.get("args", {})
    if not isinstance(args, dict):
        args = {}
    return {"action": str(name or "escalate"), "args": args}


def normalize_patch(patch: str) -> str:
    if patch and not patch.endswith("\n"):
        return patch + "\n"
    return patch


def packet_payload(packet: WorkPacketInput, context: List[FileContext]) -> Dict[str, Any]:
    payload = to_dict(packet)
    payload["context"] = [to_dict(item) for item in context]
    return payload


def verify_patch_policy(patch: str, packet: WorkPacketInput) -> WorkPacketVerification:
    warnings: List[str] = []
    changed = changed_files_from_patch(patch)
    diff_lines = count_diff_lines(patch)
    if not changed and patch.strip():
        return WorkPacketVerification(False, True, "Could not determine changed files from patch.", warnings, [], [], diff_lines)
    if diff_lines > packet.max_diff_lines:
        return WorkPacketVerification(False, True, "Patch exceeds max_diff_lines.", warnings, [], changed, diff_lines)
    disallowed = [path for path in changed if not is_allowed(path, packet.allowed_files)]
    if disallowed:
        return WorkPacketVerification(False, True, f"Patch touched files outside allowed_files: {disallowed}", warnings, [], changed, diff_lines)
    forbidden = [path for path in changed if is_forbidden(path, packet.forbidden_paths)]
    if forbidden:
        return WorkPacketVerification(False, True, f"Patch touched forbidden paths: {forbidden}", warnings, [], changed, diff_lines)
    protected = [
        path for path in changed
        if any(keyword in path.lower() for keyword in PROTECTED_PATH_KEYWORDS)
    ]
    if protected:
        return WorkPacketVerification(False, True, f"Patch touched protected paths: {protected}", warnings, [], changed, diff_lines)
    if SECRET_RE.search(patch):
        return WorkPacketVerification(False, True, "Patch appears to contain a secret.", warnings, [], changed, diff_lines)
    return WorkPacketVerification(True, False, "Patch policy passed.", warnings, [], changed, diff_lines)


def changed_files_from_patch(patch: str) -> List[str]:
    files: List[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return sorted(set(files))


def count_diff_lines(patch: str) -> int:
    return sum(1 for line in patch.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))


def is_allowed(path: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    return any(fnmatch.fnmatch(path, pattern) or path == pattern for pattern in allowed)


def is_forbidden(path: str, forbidden: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or pattern in path for pattern in forbidden)


def search_code(workspace: Path, pattern: str, raw_path: str = ".") -> Dict[str, Any]:
    if not pattern:
        return {"type": "search_result", "matches": []}
    root = safe_path(workspace, raw_path)
    if not root.exists():
        return {"type": "search_result", "matches": []}
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return {"type": "search_error", "message": f"Invalid regex: {e}"}
    matches: List[Dict[str, Any]] = []
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    for path in files:
        if should_skip(path):
            continue
        rel = str(path.relative_to(workspace))
        try:
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if regex.search(line):
                    matches.append({"path": rel, "line": lineno, "text": line[:240]})
                    break
        except OSError:
            continue
        if len(matches) >= 30:
            break
    return {"type": "search_result", "matches": matches}


def open_file(workspace: Path, raw_path: str, line: int = 1, limit: int = 120) -> Dict[str, Any]:
    path = safe_path(workspace, raw_path)
    if not path.exists() or not path.is_file():
        return {"type": "file_error", "path": raw_path, "message": "File not found."}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, line)
    end = min(len(lines), start + max(1, min(limit, 200)) - 1)
    content = [
        {"line": lineno, "text": lines[lineno - 1]}
        for lineno in range(start, end + 1)
    ]
    return {"type": "file_content", "path": raw_path, "start": start, "end": end, "lines": content}


def list_files(workspace: Path, glob: str) -> Dict[str, Any]:
    files = []
    for path in workspace.rglob(glob or "*"):
        if path.is_file() and not should_skip(path):
            files.append(str(path.relative_to(workspace)))
        if len(files) >= 100:
            break
    return {"type": "file_list", "files": sorted(files)}


def safe_path(workspace: Path, raw_path: str) -> Path:
    path = (workspace / raw_path).resolve()
    if workspace not in path.parents and path != workspace:
        raise ValueError(f"Path escapes workspace: {raw_path}")
    return path


def should_skip(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def work_packet_result(packet: WorkPacketInput, transcript: List[Dict[str, Any]],
                       verification: WorkPacketVerification,
                       result: Dict[str, Any]) -> Dict[str, Any]:
    status = "success" if verification.ok else "needs_codex"
    return {
        "route": "deepseek" if verification.ok else "codex",
        "status": status,
        "delegation_level": packet.delegation_level,
        "summary": result.get("summary", ""),
        "changed_files": verification.changed_files or result.get("changed_files", []),
        "patch": result.get("patch", ""),
        "checks": verification.executed_commands,
        "verification": to_dict(verification),
        "risk_notes": result.get("risk_notes", []),
        "preflight_satisfied": bool(result.get("preflight_satisfied")),
        "transcript": transcript,
        "metrics": {
            "iterations": len([item for item in transcript if item.get("role") == "worker"]),
            "worker_actions": len([item for item in transcript if item.get("role") == "worker"]),
            "diff_lines": verification.diff_lines,
        },
    }
