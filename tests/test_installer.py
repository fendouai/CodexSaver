from __future__ import annotations

import json
import tomllib
from pathlib import Path

from cli import main
from codexsaver.installer import (
    doctor,
    install_config,
    install_global_config,
    install_superpower_profile,
    render_mcp_config,
    write_global_launcher,
)


def test_render_mcp_config():
    text = render_mcp_config("./codexsaver_mcp.py")
    assert '[mcp_servers.codexsaver]' in text
    assert 'args = ["./codexsaver_mcp.py"]' in text


def test_render_mcp_config_escapes_windows_paths():
    text = render_mcp_config(r"C:\Users\admin\.codexsaver\codexsaver_mcp.py")
    parsed = tomllib.loads(text)
    assert parsed["mcp_servers"]["codexsaver"]["args"] == [
        r"C:\Users\admin\.codexsaver\codexsaver_mcp.py"
    ]
    assert r"C:\\Users\\admin" in text


def test_install_config_creates_file(tmp_path):
    config_path = tmp_path / ".codex" / "config.toml"
    result = install_config(str(config_path), "./codexsaver_mcp.py")
    assert result["changed"] is True
    assert config_path.exists()
    assert "codexsaver" in config_path.read_text(encoding="utf-8")


def test_install_config_replaces_existing_section(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[mcp_servers.codexsaver]\ncommand = \"python\"\nargs = [\"old.py\"]\n\n[other]\nvalue = 1\n",
        encoding="utf-8",
    )
    install_config(str(config_path), "./codexsaver_mcp.py")
    text = config_path.read_text(encoding="utf-8")
    assert 'args = ["./codexsaver_mcp.py"]' in text
    assert 'args = ["old.py"]' not in text
    assert "[other]" in text


def test_write_global_launcher_points_to_source_root(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    launcher_path = tmp_path / "home" / ".codexsaver" / "codexsaver_mcp.py"
    result = write_global_launcher(str(source_root), str(launcher_path))
    assert result["changed"] is True
    text = launcher_path.read_text(encoding="utf-8")
    assert str(source_root) in text
    assert "runpy.run_path" in text


def test_install_global_config_uses_stable_launcher(tmp_path):
    config_path = tmp_path / ".codex" / "config.toml"
    source_root = tmp_path / "source"
    source_root.mkdir()
    launcher_path = tmp_path / ".codexsaver" / "codexsaver_mcp.py"
    with monkeypatch_context_global_launcher(launcher_path):
        result = install_global_config(str(config_path), str(source_root))
    text = config_path.read_text(encoding="utf-8")
    assert result["launcher_path"] == str(launcher_path)
    assert str(launcher_path) in text
    assert result["source_root"] == str(source_root)


def test_doctor_reports_missing_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("CODEXSAVER_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.installer.CONFIG_PATH", tmp_path / "missing.json")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    result = doctor(str(tmp_path))
    assert result["script_exists"] is False
    assert "project root" in result["recommended_next_step"]
    assert result["compression_enabled"] is False
    assert result["compression_level"] == "full"


def test_cli_install_and_doctor(tmp_path, monkeypatch, capsys):
    (tmp_path / "codexsaver_mcp.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["install", "--project", "--workspace", str(tmp_path)]) == 0
    install_output = json.loads(capsys.readouterr().out)
    assert install_output["status"] == "ok"
    assert Path(install_output["actions"][0]["config_path"]).exists()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("CODEXSAVER_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.installer.CONFIG_PATH", tmp_path / ".codexsaver-config.json")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / ".codexsaver-config.json")
    assert main(["doctor", "--workspace", str(tmp_path)]) == 0
    doctor_output = json.loads(capsys.readouterr().out)
    assert doctor_output["project_config_exists"] is True
    assert doctor_output["project_config_has_codexsaver"] is True
    assert doctor_output["provider"] == "deepseek"
    assert doctor_output["provider_api_key_configured"] is True
    assert doctor_output["deepseek_api_key_configured"] is True
    assert doctor_output["deepseek_api_key_source"] == "environment:DEEPSEEK_API_KEY"


def test_cli_install_defaults_to_global(tmp_path, monkeypatch, capsys):
    (tmp_path / "codexsaver_mcp.py").write_text("print('ok')\n", encoding="utf-8")
    home = tmp_path / "home"
    launcher = home / ".codexsaver" / "codexsaver_mcp.py"
    monkeypatch.setattr("cli.Path.home", lambda: home)
    monkeypatch.setattr("codexsaver.installer.GLOBAL_LAUNCHER_PATH", launcher)
    assert main(["install", "--workspace", str(tmp_path)]) == 0
    install_output = json.loads(capsys.readouterr().out)
    action = install_output["actions"][0]
    assert action["config_path"] == str(home / ".codex" / "config.toml")
    assert action["script_path"] == str(launcher)
    assert launcher.exists()


def test_cli_auth_set(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "saved-config.json"
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    assert main([
        "auth", "set",
        "--provider", "openai",
        "--api-key", "sk-test-key",
        "--model", "gpt-test",
    ]) == 0
    auth_output = json.loads(capsys.readouterr().out)
    assert auth_output["provider"] == "openai"
    assert auth_output["provider_api_key_saved"] is True
    assert auth_output["deepseek_api_key_saved"] is False
    assert auth_output["deepseek_api_key_preview"] is None
    assert config_path.exists()


def test_cli_auth_set_local_provider_without_key(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "saved-config.json"
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    assert main(["auth", "set", "--provider", "ollama", "--model", "llama3.1"]) == 0
    auth_output = json.loads(capsys.readouterr().out)
    assert auth_output["provider"] == "ollama"
    assert auth_output["provider_api_key_saved"] is False
    assert auth_output["provider_api_key_preview"] is None
    assert auth_output["provider_base_url"] == "http://localhost:11434/v1/chat/completions"
    assert auth_output["provider_requires_api_key"] is False


def test_cli_auth_providers_lists_presets(capsys):
    assert main(["auth", "providers"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert "anthropic" in output["providers"]
    assert "deepseek" in output["providers"]
    assert output["providers"]["ollama"]["requires_api_key"] is False
    assert "openai" in output["providers"]
    assert "gemini" in output["providers"]


def test_cli_compression_show_and_set(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "saved-config.json"
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    assert main(["compression", "show"]) == 0
    show_output = json.loads(capsys.readouterr().out)
    assert show_output["compression"] == {"enabled": False, "level": "full"}

    assert main(["compression", "set", "--enabled", "true", "--level", "wenyan"]) == 0
    set_output = json.loads(capsys.readouterr().out)
    assert set_output["compression"] == {"enabled": True, "level": "wenyan"}

    assert main(["compression", "show"]) == 0
    show_output = json.loads(capsys.readouterr().out)
    assert show_output["compression"] == {"enabled": True, "level": "wenyan"}


def test_install_superpower_basic_creates_agents_only(tmp_path):
    result = install_superpower_profile(str(tmp_path), profile="basic")
    agents = tmp_path / "AGENTS.md"
    hooks = tmp_path / ".codex" / "hooks.json"
    project_config = tmp_path / ".codex" / "config.toml"
    assert result["status"] == "ok"
    assert agents.exists()
    text = agents.read_text(encoding="utf-8")
    assert "CODEXSAVER:BEGIN" in text
    assert "Prefer `codexsaver.orchestrate_task`" in text
    assert not hooks.exists()
    assert not project_config.exists()


def test_install_superpower_full_creates_hooks_and_project_config(tmp_path):
    result = install_superpower_profile(str(tmp_path), profile="full")
    agents = tmp_path / "AGENTS.md"
    hook_script = tmp_path / ".codex" / "hooks" / "codexsaver_prompt_guard.py"
    hooks_json = tmp_path / ".codex" / "hooks.json"
    project_config = tmp_path / ".codex" / "config.toml"
    assert result["status"] == "ok"
    assert agents.exists()
    assert hook_script.exists()
    assert hooks_json.exists()
    assert project_config.exists()
    hooks = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert "UserPromptSubmit" in hooks["hooks"]
    config_text = project_config.read_text(encoding="utf-8")
    assert "codex_hooks = true" in config_text


def test_install_superpower_updates_existing_agents_block_only(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Existing Rules\n\nKeep this.\n\n<!-- CODEXSAVER:BEGIN -->\nold\n<!-- CODEXSAVER:END -->\n",
        encoding="utf-8",
    )
    install_superpower_profile(str(tmp_path), profile="basic")
    text = agents.read_text(encoding="utf-8")
    assert "# Existing Rules" in text
    assert "Keep this." in text
    assert "Prefer `codexsaver.orchestrate_task`" in text
    assert "old" not in text


def test_cli_superpower_install_basic(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["superpower", "install", "--workspace", str(tmp_path), "--profile", "basic"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert output["profile"] == "basic"
    assert (tmp_path / "AGENTS.md").exists()


class monkeypatch_context_global_launcher:
    def __init__(self, launcher_path: Path):
        self.launcher_path = launcher_path
        self.previous = None

    def __enter__(self):
        import codexsaver.installer as installer

        self.previous = installer.GLOBAL_LAUNCHER_PATH
        installer.GLOBAL_LAUNCHER_PATH = self.launcher_path

    def __exit__(self, exc_type, exc, tb):
        import codexsaver.installer as installer

        installer.GLOBAL_LAUNCHER_PATH = self.previous
