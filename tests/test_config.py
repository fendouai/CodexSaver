from __future__ import annotations

from codexsaver.config import (
    load_compression_config,
    load_config,
    mask_secret,
    resolve_api_key,
    resolve_provider_config,
    save_api_key,
    save_compression_config,
    save_provider_config,
)


def test_mask_secret():
    assert mask_secret("sk-1234567890") == "sk-1...7890"


def test_save_and_load_api_key(tmp_path):
    config_path = tmp_path / "config.json"
    report = save_api_key("sk-test-value", str(config_path))
    assert report["key_preview"] == "sk-t...alue"
    assert load_config(str(config_path))["deepseek_api_key"] == "sk-test-value"
    assert load_config(str(config_path))["providers"]["deepseek"]["api_key"] == "sk-test-value"


def test_resolve_api_key_from_argument(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    api_key, source = resolve_api_key("sk-arg")
    assert api_key == "sk-arg"
    assert source == "argument"


def test_resolve_api_key_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    monkeypatch.delenv("CODEXSAVER_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    api_key, source = resolve_api_key()
    assert api_key == "sk-env"
    assert source == "environment:DEEPSEEK_API_KEY"


def test_resolve_api_key_from_local_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    save_api_key("sk-local", str(config_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    api_key, source = resolve_api_key()
    assert api_key == "sk-local"
    assert source == "local_config:deepseek"


def test_save_and_resolve_openai_provider(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    save_provider_config(
        provider="openai",
        api_key="sk-openai",
        model="gpt-test",
        config_path=str(config_path),
    )
    monkeypatch.delenv("CODEXSAVER_PROVIDER", raising=False)
    monkeypatch.delenv("CODEXSAVER_API_KEY", raising=False)
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    provider = resolve_provider_config()
    assert provider.name == "openai"
    assert provider.api_key == "sk-openai"
    assert provider.model == "gpt-test"
    assert provider.base_url == "https://api.openai.com/v1/chat/completions"


def test_generic_env_overrides_provider_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "gemini")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-generic")
    monkeypatch.setenv("CODEXSAVER_MODEL", "gemini-test")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    provider = resolve_provider_config()
    assert provider.name == "gemini"
    assert provider.api_key == "sk-generic"
    assert provider.model == "gemini-test"


def test_anthropic_preset_uses_native_messages_api(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    provider = resolve_provider_config()
    assert provider.api_style == "anthropic"
    assert provider.base_url == "https://api.anthropic.com/v1/messages"
    assert provider.api_key == "sk-ant"


def test_local_provider_can_skip_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "ollama")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    provider = resolve_provider_config()
    assert provider.requires_api_key is False
    assert provider.api_key is None


def test_custom_provider_requires_custom_base_url(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    save_provider_config(
        provider="custom",
        api_key="sk-custom",
        model="custom-model",
        base_url="https://llm.example.test/v1/chat/completions",
        config_path=str(config_path),
    )
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    provider = resolve_provider_config()
    assert provider.name == "custom"
    assert provider.base_url == "https://llm.example.test/v1/chat/completions"


def test_compression_config_defaults_to_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", tmp_path / "missing.json")
    assert load_compression_config() == {"enabled": False, "level": "full"}


def test_save_and_load_compression_config(tmp_path):
    config_path = tmp_path / "config.json"
    report = save_compression_config(enabled=True, level="ultra", config_path=str(config_path))
    assert report["compression"] == {"enabled": True, "level": "ultra"}
    assert load_compression_config(str(config_path)) == {"enabled": True, "level": "ultra"}


def test_save_compression_config_rejects_invalid_level(tmp_path):
    config_path = tmp_path / "config.json"
    try:
        save_compression_config(enabled=True, level="bad", config_path=str(config_path))
    except ValueError as exc:
        assert "Invalid compression level" in str(exc)
    else:
        raise AssertionError("expected ValueError")
