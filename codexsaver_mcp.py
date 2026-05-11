#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict

from codexsaver.engine import CodexSaverEngine

JSONRPC = "2.0"


def respond(id_: Any, result: Any = None, error: Any = None) -> None:
    msg: Dict[str, Any] = {"jsonrpc": JSONRPC, "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    print(json.dumps(msg, ensure_ascii=False), flush=True)


def delegate_task_schema() -> Dict[str, Any]:
    return {
        "name": "delegate_task",
        "description": (
            "Delegate low-risk coding tasks to a configured low-cost LLM provider to reduce Codex cost. "
            "Use for tests, docs, code search, explanations, lint fixes, boilerplate, "
            "and small refactors. Do not use for high-risk architecture/security/payment/migration tasks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "The coding task to delegate."},
                "files": {"type": "array", "items": {"type": "string"},
                          "description": "File paths to include as bounded context."},
                "constraints": {"type": "array", "items": {"type": "string"},
                                "description": "Extra safety or output constraints."},
                "workspace": {"type": "string",
                              "description": "Workspace root used to resolve relative file paths and run verification commands."},
                "max_files": {"type": "integer", "minimum": 1,
                              "description": "Maximum number of files to include in delegated context."},
                "max_chars_per_file": {"type": "integer", "minimum": 1,
                                       "description": "Maximum characters loaded per file."},
                "max_total_chars": {"type": "integer", "minimum": 1,
                                    "description": "Maximum total characters loaded across all files."},
                "dry_run": {"type": "boolean",
                            "description": "If true, only show routing decision and task preview."}
            },
            "required": ["instruction"]
        }
    }


def delegate_work_packet_schema() -> Dict[str, Any]:
    return {
        "name": "delegate_work_packet",
        "description": (
            "Delegate a bounded v2 coding work packet to a configured worker model. "
            "Use when the task has clear scope, allowed files, acceptance criteria, "
            "and allowlisted checks. The worker may inspect files, propose patches, "
            "run allowlisted checks in a sandbox, and repair within max_iterations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The bounded coding goal."},
                "files": {"type": "array", "items": {"type": "string"},
                          "description": "Initial files to include as context."},
                "allowed_files": {"type": "array", "items": {"type": "string"},
                                  "description": "Files or glob patterns the patch may touch."},
                "forbidden_paths": {"type": "array", "items": {"type": "string"},
                                    "description": "Forbidden paths or glob patterns."},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"},
                                        "description": "Evidence the work must satisfy."},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "allowed_commands": {"type": "array", "items": {"type": "string"},
                                     "description": "Exact commands the worker may run in the sandbox."},
                "workspace": {"type": "string"},
                "delegation_level": {"type": "string",
                                     "enum": ["research", "draft_patch", "bounded_impl", "repair_loop"]},
                "max_iterations": {"type": "integer", "minimum": 1, "maximum": 5},
                "max_diff_lines": {"type": "integer", "minimum": 1},
                "dry_run": {"type": "boolean"}
            },
            "required": ["goal"]
        }
    }


def handle(request: Dict[str, Any], engine: CodexSaverEngine) -> None:
    method = request.get("method")
    id_ = request.get("id")
    if method == "initialize":
        respond(id_, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                     "serverInfo": {"name": "codexsaver", "version": "0.2.0"}})
        return
    if method == "notifications/initialized":
        return
    if method == "tools/list":
        respond(id_, {"tools": [delegate_task_schema(), delegate_work_packet_schema()]})
        return
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "delegate_task":
            result = engine.delegate_task(arguments)
            respond(id_, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
            return
        if name == "delegate_work_packet":
            result = engine.delegate_work_packet(arguments)
            respond(id_, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
            return
        if name not in {"delegate_task", "delegate_work_packet"}:
            respond(id_, error={"code": -32601, "message": f"Unknown tool: {name}"})
            return
    respond(id_, error={"code": -32601, "message": f"Unsupported method: {method}"})


def main() -> int:
    engine = CodexSaverEngine()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            handle(request, engine)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            id_ = request.get("id") if "request" in locals() and isinstance(request, dict) else None
            respond(id_, error={"code": -32603, "message": str(e)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
