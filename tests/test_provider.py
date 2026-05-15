from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from codexsaver.provider import ProviderClient, ProviderError
from codexsaver.schema import WorkerTask


def test_provider_client_posts_chat_completion(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "openai")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-test")
    monkeypatch.setenv("CODEXSAVER_MODEL", "gpt-test")
    response = MagicMock()
    response.read.return_value = json.dumps({
        "choices": [{
            "message": {
                "content": json.dumps({
                    "status": "success",
                    "summary": "ok",
                    "changed_files": [],
                    "patch": "",
                    "commands_to_run": [],
                    "risk_notes": [],
                })
            }
        }]
    }).encode("utf-8")
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client = ProviderClient()
        result = client.complete_task(WorkerTask(
            instruction="explain code",
            task_type="explain",
            risk="low",
            constraints=[],
            workspace="/tmp/project",
            files=[],
        ))

    assert result["status"] == "success"
    request = urlopen.call_args[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.openai.com/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == "gpt-test"
    assert payload["messages"][0]["role"] == "system"


def test_provider_client_injects_compression_prompt(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"compression": {"enabled": True, "level": "full"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "openai")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-test")
    monkeypatch.setenv("CODEXSAVER_MODEL", "gpt-test")
    monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
    response = MagicMock()
    response.read.return_value = json.dumps({
        "choices": [{
            "message": {
                "content": json.dumps({
                    "status": "success",
                    "summary": "ok",
                    "changed_files": [],
                    "patch": "",
                    "commands_to_run": [],
                    "risk_notes": [],
                })
            }
        }]
    }).encode("utf-8")
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client = ProviderClient()
        client.complete_task(WorkerTask(
            instruction="explain code",
            task_type="explain",
            risk="low",
            constraints=[],
            workspace="/tmp/project",
            files=[],
        ))

    payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
    assert "Output compression mode" in payload["messages"][0]["content"]
    assert "compressed worker output" in payload["messages"][0]["content"]


def test_provider_client_posts_custom_json(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "openai")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-test")
    response = MagicMock()
    response.read.return_value = json.dumps({
        "choices": [{
            "message": {"content": json.dumps({"action": "finish", "args": {}})}
        }]
    }).encode("utf-8")
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client = ProviderClient()
        result = client.complete_json("system", {"hello": "world"})

    assert result["action"] == "finish"
    payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
    assert payload["messages"][0]["content"] == "system"
    assert json.loads(payload["messages"][1]["content"]) == {"hello": "world"}


def test_provider_client_posts_anthropic_messages(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    response = MagicMock()
    response.read.return_value = json.dumps({
        "content": [{
            "type": "text",
            "text": json.dumps({
                "status": "success",
                "summary": "ok",
                "changed_files": [],
                "patch": "",
                "commands_to_run": [],
                "risk_notes": [],
            }),
        }]
    }).encode("utf-8")
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client = ProviderClient()
        result = client.complete_task(WorkerTask(
            instruction="explain code",
            task_type="explain",
            risk="low",
            constraints=[],
            workspace="/tmp/project",
            files=[],
        ))

    assert result["status"] == "success"
    request = urlopen.call_args[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.headers["X-api-key"] == "sk-ant"
    assert request.headers["Anthropic-version"] == "2023-06-01"
    assert payload["system"]
    assert payload["messages"][0]["role"] == "user"


def test_provider_client_allows_local_provider_without_api_key(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "ollama")
    monkeypatch.delenv("CODEXSAVER_API_KEY", raising=False)
    client = ProviderClient()
    assert client.provider_name == "ollama"


def test_provider_client_requires_base_url_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "custom")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-test")
    monkeypatch.delenv("CODEXSAVER_BASE_URL", raising=False)
    with pytest.raises(ProviderError, match="Missing base URL"):
        ProviderClient()


def test_provider_client_requires_model_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("CODEXSAVER_PROVIDER", "custom")
    monkeypatch.setenv("CODEXSAVER_API_KEY", "sk-test")
    monkeypatch.setenv("CODEXSAVER_BASE_URL", "https://llm.example.test/v1/chat/completions")
    monkeypatch.delenv("CODEXSAVER_MODEL", raising=False)
    with pytest.raises(ProviderError, match="Missing model"):
        ProviderClient()
