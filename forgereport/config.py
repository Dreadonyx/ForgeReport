"""Configuration loading for ForgeReport."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULT_CONFIG_PATH = Path("~/.forgereport/config.yaml").expanduser()

DEFAULT_CONFIG: dict[str, Any] = {
    "default_mode": "ctf",
    "default_output": "./reports/",
    "providers": {
        "groq": {
            "api_key": "",
            "model": "llama-3.3-70b-versatile",
        },
        "openrouter": {
            "api_key": "",
            "model": "mistralai/mistral-7b-instruct:free",
        },
        "mistral": {
            "api_key": "",
            "model": "mistral-small-latest",
        },
    },
}

ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load config from YAML and environment variables."""

    load_dotenv()
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    data: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"Config file must contain a YAML mapping: {path}")
            data = loaded

    config = deep_merge(DEFAULT_CONFIG, data)
    providers = config.setdefault("providers", {})
    for provider, env_key in ENV_KEYS.items():
        env_value = os.getenv(env_key, "").strip()
        providers.setdefault(provider, {})
        if env_value:
            providers[provider]["api_key"] = env_value
        providers[provider]["env_var"] = env_key

    return config


def provider_config(config: dict[str, Any], provider: str) -> dict[str, Any]:
    return config.get("providers", {}).get(provider, {})
