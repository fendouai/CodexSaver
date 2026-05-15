#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codexsaver.engine import CodexSaverEngine
from codexsaver.config import (
    PROVIDER_PRESETS,
    load_compression_config,
    normalize_provider,
    save_compression_config,
    save_provider_config,
)
from codexsaver.installer import doctor, install_config, install_global_config, install_superpower_profile


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        return _run_subcommand(["--help"])
    if argv and argv[0] in {
        "install",
        "doctor",
        "delegate",
        "work-packet",
        "orchestrate",
        "specialist",
        "superpower",
        "auth",
        "compression",
    }:
        return _run_subcommand(argv)
    return _run_delegate(argv)


def _run_delegate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="CodexSaver CLI",
        epilog=(
            "Quick setup: `python cli.py install` then "
            "`python cli.py doctor`."
        ),
    )
    parser.add_argument("instruction")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = CodexSaverEngine().delegate_task({
        "instruction": args.instruction,
        "files": args.files,
        "constraints": args.constraint,
        "workspace": args.workspace,
        "dry_run": args.dry_run,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _run_subcommand(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="CodexSaver setup and diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser(
        "install",
        help="Write Codex MCP config for this project or globally.",
    )
    install_parser.add_argument("--workspace", default=".")
    install_parser.add_argument("--project", action="store_true")
    install_parser.add_argument("--global", dest="global_install", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check whether CodexSaver is ready in this workspace.",
    )
    doctor_parser.add_argument("--workspace", default=".")

    auth_parser = subparsers.add_parser(
        "auth",
        help="Persist worker provider settings locally.",
    )
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)
    auth_set_parser = auth_subparsers.add_parser("set", help="Save provider settings locally.")
    auth_set_parser.add_argument("--api-key")
    auth_set_parser.add_argument("--provider", default="deepseek",
                                 help="Worker provider name. Defaults to deepseek.")
    auth_set_parser.add_argument("--model",
                                 help="Optional model override for the provider.")
    auth_set_parser.add_argument("--base-url",
                                 help="Optional OpenAI-compatible chat completions URL.")

    auth_subparsers.add_parser(
        "providers",
        help="List built-in worker provider presets.",
    )

    compression_parser = subparsers.add_parser(
        "compression",
        help="View or update worker output compression settings.",
    )
    compression_subparsers = compression_parser.add_subparsers(dest="compression_command", required=True)
    compression_subparsers.add_parser("show", help="Show current compression configuration.")
    compression_set_parser = compression_subparsers.add_parser("set", help="Update compression configuration.")
    compression_set_parser.add_argument("--enabled", choices=["true", "false"], help="Enable or disable compression.")
    compression_set_parser.add_argument(
        "--level",
        choices=["lite", "full", "ultra", "wenyan"],
        help="Set compression level.",
    )

    delegate_parser = subparsers.add_parser(
        "delegate",
        help="Explicit delegation command equivalent to the default CLI mode.",
    )
    delegate_parser.add_argument("instruction")
    delegate_parser.add_argument("--files", nargs="*", default=[])
    delegate_parser.add_argument("--constraint", action="append", default=[])
    delegate_parser.add_argument("--workspace", default=".")
    delegate_parser.add_argument("--dry-run", action="store_true")

    work_packet_parser = subparsers.add_parser(
        "work-packet",
        help="Delegate a bounded v2 work packet with allowed files and checks.",
    )
    work_packet_parser.add_argument("goal")
    work_packet_parser.add_argument("--files", nargs="*", default=[])
    work_packet_parser.add_argument("--allowed-file", action="append", default=[])
    work_packet_parser.add_argument("--forbidden-path", action="append", default=[])
    work_packet_parser.add_argument("--acceptance", action="append", default=[])
    work_packet_parser.add_argument("--constraint", action="append", default=[])
    work_packet_parser.add_argument("--allowed-command", action="append", default=[])
    work_packet_parser.add_argument("--workspace", default=".")
    work_packet_parser.add_argument("--delegation-level", default="bounded_impl")
    work_packet_parser.add_argument("--max-iterations", type=int, default=3)
    work_packet_parser.add_argument("--max-diff-lines", type=int, default=300)
    work_packet_parser.add_argument("--dry-run", action="store_true")

    orchestrate_parser = subparsers.add_parser(
        "orchestrate",
        help="Preview or plan a v3 multi-worker orchestration graph.",
    )
    orchestrate_parser.add_argument("goal")
    orchestrate_parser.add_argument("--files", nargs="*", default=[])
    orchestrate_parser.add_argument("--constraint", action="append", default=[])
    orchestrate_parser.add_argument("--workspace", default=".")
    orchestrate_parser.add_argument("--max-parallel-workers", type=int, default=4)
    orchestrate_parser.add_argument("--dry-run", action="store_true")

    specialist_parser = subparsers.add_parser(
        "specialist",
        help="Preview a single v3 specialist node.",
    )
    specialist_parser.add_argument("specialist")
    specialist_parser.add_argument("goal")
    specialist_parser.add_argument("--files", nargs="*", default=[])
    specialist_parser.add_argument("--allowed-file", action="append", default=[])
    specialist_parser.add_argument("--forbidden-path", action="append", default=[])
    specialist_parser.add_argument("--acceptance", action="append", default=[])
    specialist_parser.add_argument("--allowed-command", action="append", default=[])
    specialist_parser.add_argument("--workspace", default=".")
    specialist_parser.add_argument("--dry-run", action="store_true")

    superpower_parser = subparsers.add_parser(
        "superpower",
        help="Install optional project guidance such as AGENTS.md and hook scaffolding.",
    )
    superpower_subparsers = superpower_parser.add_subparsers(dest="superpower_command", required=True)
    superpower_install = superpower_subparsers.add_parser(
        "install",
        help="Install a basic or full CodexSaver project guidance profile.",
    )
    superpower_install.add_argument("--workspace", default=".")
    superpower_install.add_argument("--profile", choices=["basic", "full"], default="basic")
    superpower_install.add_argument("--with-agents", action="store_true")
    superpower_install.add_argument("--with-hooks", action="store_true")
    superpower_install.add_argument("--with-project-config", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "install":
        workspace = Path(args.workspace).resolve()
        install_project = args.project
        install_global = args.global_install or not args.project
        reports = []
        if install_project:
            reports.append(install_config(
                str(workspace / ".codex" / "config.toml"),
                "./codexsaver_mcp.py",
            ))
        if install_global:
            reports.append(install_global_config(
                str(Path.home() / ".codex" / "config.toml"),
                str(workspace),
            ))
        print(json.dumps({
            "status": "ok",
            "workspace": str(workspace),
            "actions": reports,
            "next_step": "Run `python cli.py doctor` to verify the installation.",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        print(json.dumps(doctor(args.workspace), ensure_ascii=False, indent=2))
        return 0

    if args.command == "auth":
        if args.auth_command == "providers":
            print(json.dumps({
                "status": "ok",
                "providers": {
                    name: {
                        "model": preset.model,
                        "base_url": preset.base_url,
                        "env_keys": list(preset.env_keys),
                        "api_style": preset.api_style,
                        "requires_api_key": preset.requires_api_key,
                    }
                    for name, preset in sorted(PROVIDER_PRESETS.items())
                },
                "custom": "Use --provider custom --base-url https://.../chat/completions",
            }, ensure_ascii=False, indent=2))
            return 0

        provider_name = normalize_provider(args.provider)
        preset = PROVIDER_PRESETS.get(provider_name)
        if not args.api_key and (preset is None or preset.requires_api_key):
            parser.error("--api-key is required for this provider")

        report = save_provider_config(
            provider=args.provider,
            api_key=args.api_key,
            model=args.model,
            base_url=args.base_url,
        )
        print(json.dumps({
            "status": "ok",
            "config_path": report["config_path"],
            "provider": report["provider"],
            "provider_api_key_saved": bool(args.api_key),
            "provider_api_key_preview": report["key_preview"],
            "provider_model": report["model"],
            "provider_base_url": report["base_url"],
            "provider_api_style": report["api_style"],
            "provider_requires_api_key": report["requires_api_key"],
            "deepseek_api_key_saved": report["provider"] == "deepseek",
            "deepseek_api_key_preview": (
                report["key_preview"] if report["provider"] == "deepseek" else None
            ),
            "next_step": "Run `python cli.py doctor` to verify CodexSaver can see the saved key.",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compression":
        if args.compression_command == "show":
            print(json.dumps({
                "status": "ok",
                "config_path": str(Path.home() / ".codexsaver" / "config.json"),
                "compression": load_compression_config(),
            }, ensure_ascii=False, indent=2))
            return 0

        enabled = None if args.enabled is None else args.enabled == "true"
        report = save_compression_config(enabled=enabled, level=args.level)
        print(json.dumps({
            "status": "ok",
            "config_path": report["config_path"],
            "compression": report["compression"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "superpower":
        apply_agents = args.with_agents or None
        apply_hooks = args.with_hooks or None
        apply_project_config = args.with_project_config or None
        result = install_superpower_profile(
            workspace=args.workspace,
            profile=args.profile,
            apply_agents=apply_agents,
            apply_hooks=apply_hooks,
            apply_project_config=apply_project_config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "work-packet":
        result = CodexSaverEngine().delegate_work_packet({
            "goal": args.goal,
            "files": args.files,
            "constraints": args.constraint,
            "acceptance_criteria": args.acceptance,
            "allowed_files": args.allowed_file,
            "forbidden_paths": args.forbidden_path,
            "allowed_commands": args.allowed_command,
            "workspace": args.workspace,
            "delegation_level": args.delegation_level,
            "max_iterations": args.max_iterations,
            "max_diff_lines": args.max_diff_lines,
            "dry_run": args.dry_run,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "orchestrate":
        result = CodexSaverEngine().orchestrate_task({
            "goal": args.goal,
            "files": args.files,
            "constraints": args.constraint,
            "workspace": args.workspace,
            "max_parallel_workers": args.max_parallel_workers,
            "dry_run": args.dry_run,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "specialist":
        result = CodexSaverEngine().run_specialist({
            "specialist": args.specialist,
            "goal": args.goal,
            "files": args.files,
            "allowed_files": args.allowed_file,
            "forbidden_paths": args.forbidden_path,
            "acceptance_criteria": args.acceptance,
            "allowed_commands": args.allowed_command,
            "workspace": args.workspace,
            "dry_run": args.dry_run,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = CodexSaverEngine().delegate_task({
        "instruction": args.instruction,
        "files": args.files,
        "constraints": args.constraint,
        "workspace": args.workspace,
        "dry_run": args.dry_run,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
