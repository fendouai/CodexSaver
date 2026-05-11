from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict

from .config import ProviderConfig, resolve_provider_config
from .schema import WorkerTask, to_dict


class ProviderError(RuntimeError):
    pass


SYSTEM_PROMPT = """
You are CodexSaver's low-cost coding worker.

You are NOT the final authority. Codex will review your output.

Rules:
- Return valid JSON only. No markdown fences.
- Prefer small, reviewable patches.
- Do not claim tests passed unless test output is provided.
- If the task is risky, ambiguous, or requires architecture judgment, return status="needs_codex".
- Do not modify production logic when the instruction only asks for tests/docs.
- Use unified diff format in the patch field when proposing code changes.

Required JSON shape:
{
  "status": "success | failed | needs_codex",
  "summary": "short summary",
  "changed_files": ["path"],
  "patch": "unified diff or empty string",
  "commands_to_run": ["command"],
  "risk_notes": ["note"]
}
""".strip()


class ProviderClient:
    """Small stdlib client for low-cost worker LLM providers."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        timeout_seconds: int = 120,
    ):
        self.config: ProviderConfig = resolve_provider_config(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        self.timeout_seconds = timeout_seconds
        if self.config.requires_api_key and not self.config.api_key:
            raise ProviderError(
                "Missing worker API key. Run "
                "`python cli.py auth set --provider PROVIDER --api-key ...` "
                "or set CODEXSAVER_API_KEY / provider-specific API key env vars."
            )
        if not self.config.base_url:
            raise ProviderError(
                f"Missing base URL for provider '{self.config.name}'. "
                "Use `python cli.py auth set --provider custom --base-url ... --api-key ...`."
            )
        if self.config.model == "default":
            raise ProviderError(
                f"Missing model for provider '{self.config.name}'. "
                "Use `python cli.py auth set --provider custom --model ... --base-url ... --api-key ...`."
            )

    @property
    def provider_name(self) -> str:
        return self.config.name

    def complete_task(self, task: WorkerTask) -> Dict[str, Any]:
        return self.complete_json(SYSTEM_PROMPT, to_dict(task))

    def complete_json(self, system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.config.api_style == "anthropic":
            return self._complete_anthropic_json(system_prompt, payload)
        request_payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
        }
        body = self._post(request_payload)
        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            raise ProviderError(
                f"Failed to parse {self.config.name} response: {body[:1000]}"
            ) from e

    def _post(self, payload: Dict[str, Any]) -> str:
        request = urllib.request.Request(
            self.config.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"{self.config.name} HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise ProviderError(f"{self.config.name} connection failed: {e}") from e

    def _complete_anthropic_json(self, system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "model": self.config.model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
            ],
        }
        body = self._post(payload)
        try:
            data = json.loads(body)
            content = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            return json.loads(content)
        except Exception as e:
            raise ProviderError(
                f"Failed to parse {self.config.name} response: {body[:1000]}"
            ) from e

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_style == "anthropic":
            headers["x-api-key"] = self.config.api_key or ""
            headers["anthropic-version"] = "2023-06-01"
            return headers
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


OpenAICompatibleClient = ProviderClient
