from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from .config import CONFIG_DIR, CONFIG_PATH, load_compression_config, mask_secret, resolve_provider_config

SECTION_RE = re.compile(
    r"(?ms)^\[mcp_servers\.codexsaver\]\n.*?(?=^\[|\Z)"
)
FEATURES_SECTION_RE = re.compile(
    r"(?ms)^\[features\]\n.*?(?=^\[|\Z)"
)

GLOBAL_LAUNCHER_PATH = CONFIG_DIR / "codexsaver_mcp.py"
AGENTS_BEGIN = "<!-- CODEXSAVER:BEGIN -->"
AGENTS_END = "<!-- CODEXSAVER:END -->"


def render_mcp_config(script_path: str) -> str:
    return (
        "[mcp_servers.codexsaver]\n"
        f"command = {_toml_string('python')}\n"
        f"args = [{_toml_string(script_path)}]\n"
        "startup_timeout_sec = 10\n"
        "tool_timeout_sec = 120\n"
    )


def _toml_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def install_config(config_path: str, script_path: str) -> Dict[str, Any]:
    path = Path(config_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    new_section = render_mcp_config(script_path).rstrip() + "\n"
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else ""
    replaced = bool(SECTION_RE.search(previous))
    if replaced:
        updated = SECTION_RE.sub(new_section, previous, count=1)
    else:
        updated = previous
        if updated and not updated.endswith("\n"):
            updated += "\n"
        updated += new_section
    changed = updated != previous
    if changed:
        path.write_text(updated, encoding="utf-8")
    return {
        "config_path": str(path),
        "script_path": script_path,
        "changed": changed,
        "mode": "updated" if replaced else "created",
    }


def install_global_config(config_path: str, source_root: str) -> Dict[str, Any]:
    launcher = write_global_launcher(source_root)
    config = install_config(config_path, launcher["launcher_path"])
    return {
        **config,
        "launcher_path": launcher["launcher_path"],
        "launcher_changed": launcher["changed"],
        "source_root": str(Path(source_root).resolve()),
    }


def write_global_launcher(source_root: str,
                          launcher_path: str | None = None) -> Dict[str, Any]:
    root = Path(source_root).resolve()
    launcher = Path(launcher_path).expanduser() if launcher_path else GLOBAL_LAUNCHER_PATH
    launcher.parent.mkdir(parents=True, exist_ok=True)
    text = _render_global_launcher(root)
    previous = launcher.read_text(encoding="utf-8") if launcher.exists() else ""
    changed = previous != text
    if changed:
        launcher.write_text(text, encoding="utf-8")
        launcher.chmod(0o700)
    return {
        "launcher_path": str(launcher),
        "source_root": str(root),
        "changed": changed,
    }


def _render_global_launcher(source_root: Path) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SOURCE_ROOT = Path({str(source_root)!r})
MCP_SCRIPT = SOURCE_ROOT / "codexsaver_mcp.py"

if not MCP_SCRIPT.exists():
    raise SystemExit(f"CodexSaver MCP script not found: {{MCP_SCRIPT}}")

sys.path.insert(0, str(SOURCE_ROOT))
runpy.run_path(str(MCP_SCRIPT), run_name="__main__")
"""


def doctor(workspace: str) -> Dict[str, Any]:
    root = Path(workspace).resolve()
    script_path = root / "codexsaver_mcp.py"
    project_config = root / ".codex" / "config.toml"
    global_config = Path.home() / ".codex" / "config.toml"
    project_config_has_codexsaver = _has_codexsaver_section(project_config)
    global_config_has_codexsaver = _has_codexsaver_section(global_config)
    provider = resolve_provider_config()
    compression = load_compression_config()
    return {
        "workspace": str(root),
        "script_exists": script_path.exists(),
        "script_path": str(script_path),
        "project_config_path": str(project_config),
        "project_config_exists": project_config.exists(),
        "project_config_has_codexsaver": project_config_has_codexsaver,
        "global_config_path": str(global_config),
        "global_config_exists": global_config.exists(),
        "global_config_has_codexsaver": global_config_has_codexsaver,
        "global_launcher_path": str(GLOBAL_LAUNCHER_PATH),
        "global_launcher_exists": GLOBAL_LAUNCHER_PATH.exists(),
        "local_config_path": str(CONFIG_PATH),
        "local_config_exists": CONFIG_PATH.exists(),
        "provider": provider.name,
        "provider_model": provider.model,
        "provider_model_source": provider.model_source,
        "provider_base_url": provider.base_url,
        "provider_base_url_source": provider.base_url_source,
        "provider_api_style": provider.api_style,
        "provider_requires_api_key": provider.requires_api_key,
        "provider_api_key_configured": bool(provider.api_key),
        "provider_api_key_source": provider.api_key_source,
        "provider_api_key_preview": mask_secret(provider.api_key),
        "deepseek_api_key_configured": bool(provider.api_key),
        "deepseek_api_key_source": provider.api_key_source,
        "deepseek_api_key_preview": mask_secret(provider.api_key),
        "compression_enabled": compression["enabled"],
        "compression_level": compression["level"],
        "project_agents_path": str(root / "AGENTS.md"),
        "project_agents_has_codexsaver_block": _has_codexsaver_agents_block(root / "AGENTS.md"),
        "project_hooks_path": str(root / ".codex" / "hooks.json"),
        "project_hooks_exists": (root / ".codex" / "hooks.json").exists(),
        "project_hooks_enabled": _has_feature_flag(root / ".codex" / "config.toml", "codex_hooks"),
        "recommended_next_step": _recommended_next_step(
            script_exists=script_path.exists(),
            codexsaver_installed=project_config_has_codexsaver or global_config_has_codexsaver,
            api_key_configured=bool(provider.api_key) or not provider.requires_api_key,
        ),
    }


def install_superpower_profile(workspace: str, profile: str = "basic",
                               apply_agents: bool | None = None,
                               apply_hooks: bool | None = None,
                               apply_project_config: bool | None = None) -> Dict[str, Any]:
    root = Path(workspace).resolve()
    profile = profile.lower()
    if profile not in {"basic", "full"}:
        raise ValueError("profile must be 'basic' or 'full'")

    if apply_agents is None:
        apply_agents = True
    if apply_hooks is None:
        apply_hooks = profile == "full"
    if apply_project_config is None:
        apply_project_config = profile == "full"

    actions = []

    if apply_agents:
        actions.append(_install_agents_guidance(root, profile))

    hook_script_path = root / ".codex" / "hooks" / "codexsaver_prompt_guard.py"
    if apply_hooks:
        actions.append(_write_hook_script(hook_script_path))
        actions.append(_merge_hooks_json(root / ".codex" / "hooks.json", hook_script_path))

    if apply_project_config:
        actions.append(_enable_codex_hooks_feature(root / ".codex" / "config.toml"))

    return {
        "status": "ok",
        "workspace": str(root),
        "profile": profile,
        "actions": actions,
        "notes": _superpower_notes(profile, apply_hooks, apply_project_config),
    }


def _has_codexsaver_section(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(SECTION_RE.search(path.read_text(encoding="utf-8")))


def _has_codexsaver_agents_block(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return AGENTS_BEGIN in text and AGENTS_END in text


def _has_feature_flag(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    section = FEATURES_SECTION_RE.search(text)
    if not section:
        return False
    return re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*true\s*$", section.group(0)) is not None


def _install_agents_guidance(root: Path, profile: str) -> Dict[str, Any]:
    path = root / "AGENTS.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    block = _render_agents_block(root.name, profile)
    managed = f"{AGENTS_BEGIN}\n{block.rstrip()}\n{AGENTS_END}\n"
    if AGENTS_BEGIN in previous and AGENTS_END in previous:
        updated = re.sub(
            rf"(?s){re.escape(AGENTS_BEGIN)}.*?{re.escape(AGENTS_END)}\n?",
            managed,
            previous,
        )
        mode = "updated"
    else:
        updated = previous
        if updated and not updated.endswith("\n"):
            updated += "\n"
        if updated:
            updated += "\n"
        updated += managed
        mode = "created" if not previous else "extended"
    changed = updated != previous
    if changed:
        path.write_text(updated, encoding="utf-8")
    return {
        "type": "agents",
        "path": str(path),
        "changed": changed,
        "mode": mode,
    }


def _render_agents_block(project_name: str, profile: str) -> str:
    body = [
        "---",
        'version: "1.0"',
        f'project_name: "{project_name}"',
        f'codexsaver_profile: "{profile}"',
        "---",
        "",
        "# CodexSaver Workflow",
        "",
        "## Tool Priority",
        "",
        "- Prefer `codexsaver.orchestrate_task` for decomposable low-risk work spanning docs, tests, explanation, or bounded implementation.",
        "- Prefer `codexsaver.run_specialist` for an explicit specialist task such as explanation or tests only.",
        "- Prefer `codexsaver.delegate_work_packet` for a single bounded patch with explicit allowed files and checks.",
        "- Fall back to direct Codex execution only when CodexSaver returns `needs_codex`, fails repeatedly, or the task touches a protected domain.",
        "",
        "## Low-Risk Tasks That Should Usually Use CodexSaver",
        "",
        "- unit tests",
        "- docstrings, JSDoc, README updates",
        "- code explanation and repository scanning",
        "- formatting and boilerplate",
        "- small bounded refactors with explicit file scope",
        "",
        "## Do Not Route To CodexSaver By Default",
        "",
        "- auth, security, payment, permissions, secrets",
        "- destructive migrations or deploy logic",
        "- ambiguous architecture decisions",
        "- final merge judgment without Codex review",
        "",
        "## Verification Expectations",
        "",
        "- When CodexSaver returns checks, review them before applying changes.",
        "- Prefer allowlisted test or lint commands for generated tests and docs updates.",
        "- If CodexSaver reports overlapping patch outputs or protected-path conflicts, keep the task in Codex.",
    ]
    if profile == "full":
        body.extend([
            "",
            "## Full Profile Notes",
            "",
            "- This project opts into the CodexSaver prompt hook for additional low-risk routing guidance.",
            "- Keep hook-generated guidance advisory; Codex remains responsible for final judgment.",
        ])
    return "\n".join(body)


def _write_hook_script(path: Path) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = """#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

LOW_RISK_HINT = (
    "Prefer CodexSaver MCP tools for low-risk tests, docs, explanation, formatting, "
    "and bounded implementation work. Keep auth, security, payment, migrations, "
    "and ambiguous architecture work in Codex."
)

KEYWORDS = [
    "test", "pytest", "doc", "readme", "explain", "format", "refactor",
    "单测", "测试", "文档", "解释", "格式化", "重构",
]


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    prompt = str(payload.get("prompt", ""))
    if not any(word in prompt.lower() for word in KEYWORDS):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": LOW_RISK_HINT,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    changed = previous != text
    if changed:
        path.write_text(text, encoding="utf-8")
        path.chmod(0o700)
    return {
        "type": "hook_script",
        "path": str(path),
        "changed": changed,
        "mode": "updated" if previous else "created",
    }


def _merge_hooks_json(path: Path, hook_script_path: Path) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    data = json.loads(previous) if previous.strip() else {"description": "CodexSaver hooks", "hooks": {}}
    hooks = data.setdefault("hooks", {})
    user_prompt_hooks = hooks.setdefault("UserPromptSubmit", [])
    command = f'python ".codex/hooks/{hook_script_path.name}"'
    exists = any(
        item.get("hooks", [{}])[0].get("command") == command
        for item in user_prompt_hooks
        if item.get("hooks")
    )
    if not exists:
        user_prompt_hooks.append({
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": 5,
                }
            ],
        })
    updated = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    changed = updated != previous
    if changed:
        path.write_text(updated, encoding="utf-8")
    return {
        "type": "hooks_json",
        "path": str(path),
        "changed": changed,
        "mode": "updated" if previous else "created",
    }


def _enable_codex_hooks_feature(path: Path) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    section = FEATURES_SECTION_RE.search(previous)
    new_line = "codex_hooks = true\n"
    if section:
        block = section.group(0)
        if re.search(r"(?m)^\s*codex_hooks\s*=", block):
            updated_block = re.sub(r"(?m)^\s*codex_hooks\s*=.*$", new_line.rstrip(), block)
        else:
            updated_block = block + ("" if block.endswith("\n") else "\n") + new_line
        updated = previous[:section.start()] + updated_block + previous[section.end():]
        mode = "updated"
    else:
        updated = previous
        if updated and not updated.endswith("\n"):
            updated += "\n"
        updated += "[features]\n" + new_line
        mode = "created" if not previous else "extended"
    changed = updated != previous
    if changed:
        path.write_text(updated, encoding="utf-8")
    return {
        "type": "project_config",
        "path": str(path),
        "changed": changed,
        "mode": mode,
    }


def _superpower_notes(profile: str, apply_hooks: bool, apply_project_config: bool) -> list[str]:
    notes = [
        "Basic profile keeps changes minimal and project-local.",
        "CodexSaver guidance is inserted as a managed block so reruns replace only that block.",
    ]
    if apply_hooks:
        notes.append("Hooks are advisory and currently rely on Codex hook support being enabled.")
    if apply_project_config:
        notes.append("Project config was updated locally to enable codex_hooks; no global config was modified.")
    if profile == "full":
        notes.append("Full profile is more invasive than basic because it writes .codex/hooks.json and project feature flags.")
    return notes


def _recommended_next_step(script_exists: bool, codexsaver_installed: bool,
                           api_key_configured: bool) -> str:
    if not script_exists:
        return "Run this command from the CodexSaver project root."
    if not codexsaver_installed:
        return "Run `codexsaver install` to enable CodexSaver in every Codex workspace."
    if not api_key_configured:
        return "Run `codexsaver auth set --provider deepseek --api-key ...` before live delegated calls."
    return "CodexSaver is ready. Open this workspace in Codex and call codexsaver.delegate_task."
