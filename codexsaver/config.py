from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


CONFIG_DIR = Path.home() / ".codexsaver"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass(frozen=True)
class ProviderPreset:
    name: str
    base_url: str
    model: str
    env_keys: tuple[str, ...]
    api_style: str = "openai"
    requires_api_key: bool = True


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None
    api_key_source: str | None
    base_url: str | None
    base_url_source: str | None
    model: str
    model_source: str
    api_style: str
    requires_api_key: bool


COMPRESSION_LEVELS = ("lite", "full", "ultra", "wenyan")
DEFAULT_COMPRESSION_CONFIG = {
    "enabled": False,
    "level": "full",
}


PROVIDER_PRESETS: Dict[str, ProviderPreset] = {
    "deepseek": ProviderPreset(
        name="deepseek",
        base_url="https://api.deepseek.com/chat/completions",
        model="deepseek-chat",
        env_keys=("DEEPSEEK_API_KEY",),
    ),
    "openai": ProviderPreset(
        name="openai",
        base_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        env_keys=("OPENAI_API_KEY",),
    ),
    "anthropic": ProviderPreset(
        name="anthropic",
        base_url="https://api.anthropic.com/v1/messages",
        model="claude-3-5-haiku-latest",
        env_keys=("ANTHROPIC_API_KEY",),
        api_style="anthropic",
    ),
    "openrouter": ProviderPreset(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1/chat/completions",
        model="deepseek/deepseek-chat-v3-0324:free",
        env_keys=("OPENROUTER_API_KEY",),
    ),
    "gemini": ProviderPreset(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        model="gemini-2.0-flash",
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    ),
    "qwen": ProviderPreset(
        name="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        model="qwen-plus",
        env_keys=("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    ),
    "moonshot": ProviderPreset(
        name="moonshot",
        base_url="https://api.moonshot.cn/v1/chat/completions",
        model="moonshot-v1-8k",
        env_keys=("MOONSHOT_API_KEY",),
    ),
    "zhipu": ProviderPreset(
        name="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        model="glm-4-flash",
        env_keys=("ZHIPU_API_KEY",),
    ),
    "groq": ProviderPreset(
        name="groq",
        base_url="https://api.groq.com/openai/v1/chat/completions",
        model="llama-3.1-8b-instant",
        env_keys=("GROQ_API_KEY",),
    ),
    "mistral": ProviderPreset(
        name="mistral",
        base_url="https://api.mistral.ai/v1/chat/completions",
        model="mistral-small-latest",
        env_keys=("MISTRAL_API_KEY",),
    ),
    "xai": ProviderPreset(
        name="xai",
        base_url="https://api.x.ai/v1/chat/completions",
        model="grok-3-mini",
        env_keys=("XAI_API_KEY",),
    ),
    "together": ProviderPreset(
        name="together",
        base_url="https://api.together.xyz/v1/chat/completions",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        env_keys=("TOGETHER_API_KEY",),
    ),
    "fireworks": ProviderPreset(
        name="fireworks",
        base_url="https://api.fireworks.ai/inference/v1/chat/completions",
        model="accounts/fireworks/models/llama-v3p1-8b-instruct",
        env_keys=("FIREWORKS_API_KEY",),
    ),
    "perplexity": ProviderPreset(
        name="perplexity",
        base_url="https://api.perplexity.ai/chat/completions",
        model="sonar",
        env_keys=("PERPLEXITY_API_KEY",),
    ),
    "cohere": ProviderPreset(
        name="cohere",
        base_url="https://api.cohere.com/compatibility/v1/chat/completions",
        model="command-r7b-12-2024",
        env_keys=("COHERE_API_KEY",),
    ),
    "ollama": ProviderPreset(
        name="ollama",
        base_url="http://localhost:11434/v1/chat/completions",
        model="llama3.1",
        env_keys=(),
        requires_api_key=False,
    ),
    "lmstudio": ProviderPreset(
        name="lmstudio",
        base_url="http://localhost:1234/v1/chat/completions",
        model="local-model",
        env_keys=(),
        requires_api_key=False,
    ),
}


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    path = Path(config_path).expanduser() if config_path else CONFIG_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_config(data: Dict[str, Any], config_path: str | None = None) -> str:
    path = Path(config_path).expanduser() if config_path else CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return str(path)


def normalize_provider(provider: str | None) -> str:
    return (provider or "deepseek").strip().lower().replace("_", "-")


def provider_env_prefix(provider: str) -> str:
    return normalize_provider(provider).replace("-", "_").upper()


def save_provider_config(
    provider: str = "deepseek",
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    config_path: str | None = None,
) -> Dict[str, Any]:
    config = load_config(config_path)
    provider_name = normalize_provider(provider)
    config["provider"] = provider_name
    providers = config.setdefault("providers", {})
    provider_config = providers.setdefault(provider_name, {})
    if api_key is not None:
        provider_config["api_key"] = api_key
    if model is not None:
        provider_config["model"] = model
    if base_url is not None:
        provider_config["base_url"] = base_url
    if provider_name == "deepseek" and api_key is not None:
        config["deepseek_api_key"] = api_key
    path = save_config(config, config_path)
    preset = PROVIDER_PRESETS.get(provider_name)
    return {
        "config_path": path,
        "provider": provider_name,
        "key_preview": mask_secret(api_key),
        "model": provider_config.get("model") or (preset.model if preset else None),
        "base_url": provider_config.get("base_url") or (preset.base_url if preset else None),
        "api_style": preset.api_style if preset else "openai",
        "requires_api_key": preset.requires_api_key if preset else True,
    }


def load_compression_config(config_path: str | None = None) -> Dict[str, Any]:
    config = load_config(config_path)
    compression = config.get("compression")
    if not isinstance(compression, dict):
        return dict(DEFAULT_COMPRESSION_CONFIG)
    enabled = bool(compression.get("enabled", False))
    level = str(compression.get("level", DEFAULT_COMPRESSION_CONFIG["level"])).strip().lower()
    if level not in COMPRESSION_LEVELS:
        level = DEFAULT_COMPRESSION_CONFIG["level"]
    return {
        "enabled": enabled,
        "level": level,
    }


def save_compression_config(
    *,
    enabled: bool | None = None,
    level: str | None = None,
    config_path: str | None = None,
) -> Dict[str, Any]:
    config = load_config(config_path)
    compression = config.setdefault("compression", {})
    if enabled is not None:
        compression["enabled"] = bool(enabled)
    else:
        compression.setdefault("enabled", DEFAULT_COMPRESSION_CONFIG["enabled"])
    if level is not None:
        normalized_level = str(level).strip().lower()
        if normalized_level not in COMPRESSION_LEVELS:
            raise ValueError(f"Invalid compression level: {level}")
        compression["level"] = normalized_level
    else:
        current_level = str(compression.get("level", DEFAULT_COMPRESSION_CONFIG["level"])).strip().lower()
        compression["level"] = current_level if current_level in COMPRESSION_LEVELS else DEFAULT_COMPRESSION_CONFIG["level"]
    path = save_config(config, config_path)
    resolved = load_compression_config(path)
    return {
        "config_path": path,
        "compression": resolved,
    }


def save_api_key(api_key: str, config_path: str | None = None,
                 provider: str = "deepseek") -> Dict[str, Any]:
    return save_provider_config(provider=provider, api_key=api_key, config_path=config_path)


def resolve_provider_name(explicit_provider: str | None = None) -> tuple[str, str]:
    if explicit_provider:
        return normalize_provider(explicit_provider), "argument"
    env_provider = os.environ.get("CODEXSAVER_PROVIDER")
    if env_provider:
        return normalize_provider(env_provider), "environment"
    config_provider = load_config().get("provider")
    if config_provider:
        return normalize_provider(config_provider), "local_config"
    return "deepseek", "default"


def provider_specific_env_names(provider: str) -> tuple[str, str, str]:
    prefix = provider_env_prefix(provider)
    return f"{prefix}_API_KEY", f"{prefix}_BASE_URL", f"{prefix}_MODEL"


def resolve_api_key(explicit_api_key: str | None = None,
                    provider: str | None = None) -> tuple[str | None, str | None]:
    if explicit_api_key:
        return explicit_api_key, "argument"
    provider_name, _ = resolve_provider_name(provider)
    generic_env_key = os.environ.get("CODEXSAVER_API_KEY")
    if generic_env_key:
        return generic_env_key, "environment:CODEXSAVER_API_KEY"
    preset = PROVIDER_PRESETS.get(provider_name)
    api_key_env, _, _ = provider_specific_env_names(provider_name)
    for env_name in (api_key_env, *(preset.env_keys if preset else ())):
        env_api_key = os.environ.get(env_name)
        if env_api_key:
            return env_api_key, f"environment:{env_name}"
    config = load_config()
    config_api_key = (
        config.get("providers", {}).get(provider_name, {}).get("api_key")
    )
    if config_api_key:
        return config_api_key, f"local_config:{provider_name}"
    config_api_key = config.get("deepseek_api_key") if provider_name == "deepseek" else None
    if config_api_key:
        return config_api_key, "local_config:legacy_deepseek"
    return None, None


def resolve_provider_config(
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> ProviderConfig:
    provider_name, _ = resolve_provider_name(provider)
    config = load_config()
    configured_provider = config.get("providers", {}).get(provider_name, {})
    preset = PROVIDER_PRESETS.get(provider_name)
    _, base_url_env, model_env = provider_specific_env_names(provider_name)

    resolved_api_key, api_key_source = resolve_api_key(api_key, provider_name)

    if base_url:
        resolved_base_url, base_url_source = base_url, "argument"
    elif os.environ.get("CODEXSAVER_BASE_URL"):
        resolved_base_url, base_url_source = os.environ["CODEXSAVER_BASE_URL"], "environment:CODEXSAVER_BASE_URL"
    elif os.environ.get(base_url_env):
        resolved_base_url, base_url_source = os.environ[base_url_env], f"environment:{base_url_env}"
    elif configured_provider.get("base_url"):
        resolved_base_url, base_url_source = configured_provider["base_url"], f"local_config:{provider_name}"
    elif preset:
        resolved_base_url, base_url_source = preset.base_url, "preset"
    else:
        resolved_base_url, base_url_source = None, None

    if model:
        resolved_model, model_source = model, "argument"
    elif os.environ.get("CODEXSAVER_MODEL"):
        resolved_model, model_source = os.environ["CODEXSAVER_MODEL"], "environment:CODEXSAVER_MODEL"
    elif os.environ.get(model_env):
        resolved_model, model_source = os.environ[model_env], f"environment:{model_env}"
    elif configured_provider.get("model"):
        resolved_model, model_source = configured_provider["model"], f"local_config:{provider_name}"
    elif preset:
        resolved_model, model_source = preset.model, "preset"
    else:
        resolved_model, model_source = "default", "default"

    return ProviderConfig(
        name=provider_name,
        api_key=resolved_api_key,
        api_key_source=api_key_source,
        base_url=resolved_base_url,
        base_url_source=base_url_source,
        model=resolved_model,
        model_source=model_source,
        api_style=preset.api_style if preset else "openai",
        requires_api_key=preset.requires_api_key if preset else True,
    )


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
