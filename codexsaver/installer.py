from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from .config import CONFIG_DIR, CONFIG_PATH, mask_secret, resolve_provider_config
from .config import load_compression_config

SECTION_RE = re.compile(
    r"(?ms)^\[mcp_servers\.codexsaver\]\n.*?(?=^\[|\Z)"
)

GLOBAL_LAUNCHER_PATH = CONFIG_DIR / "codexsaver_mcp.py"


def render_mcp_config(script_path: str) -> str:
    return (
        "[mcp_servers.codexsaver]\n"
        'command = "python"\n'
        f'args = ["{script_path}"]\n'
        "startup_timeout_sec = 10\n"
        "tool_timeout_sec = 120\n"
    )


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
        "recommended_next_step": _recommended_next_step(
            script_exists=script_path.exists(),
            codexsaver_installed=project_config_has_codexsaver or global_config_has_codexsaver,
            api_key_configured=bool(provider.api_key) or not provider.requires_api_key,
        ),
    }


def _has_codexsaver_section(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(SECTION_RE.search(path.read_text(encoding="utf-8")))


def _recommended_next_step(script_exists: bool, codexsaver_installed: bool,
                           api_key_configured: bool) -> str:
    if not script_exists:
        return "Run this command from the CodexSaver project root."
    if not codexsaver_installed:
        return "Run `python cli.py install` to enable CodexSaver in every Codex workspace."
    if not api_key_configured:
        return "Run `python cli.py auth set --provider deepseek --api-key ...` before live delegated calls."
    return "CodexSaver is ready. Open this workspace in Codex and call codexsaver.delegate_task."
