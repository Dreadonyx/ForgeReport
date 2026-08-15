"""LLM provider chain for ForgeReport."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from forgereport.config import ENV_KEYS
from forgereport.core.prompt import SYSTEM_PROMPT

PROVIDER_ORDER = ["groq", "openrouter", "mistral"]

PROVIDER_DEFAULTS = {
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model": "mistralai/mistral-7b-instruct:free",
    },
    "mistral": {
        "endpoint": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
    },
}


class NoProviderConfigured(RuntimeError):
    """Raised when no usable API keys are configured."""


class ProvidersExhausted(RuntimeError):
    """Raised when all configured providers fail."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("All configured providers failed: " + "; ".join(errors))


@dataclass
class ProviderStatus:
    name: str
    model: str
    api_key_present: bool
    status: str


@dataclass
class ChatProvider:
    name: str
    endpoint: str
    model: str
    api_key: str

    def headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/forgereport"
        return headers

    def complete(self, user_prompt: str, timeout: int = 90) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(
            self.endpoint,
            headers=self.headers(),
            json=payload,
            timeout=timeout,
        )
        if response.status_code == 429:
            raise RateLimitError(f"{self.name} rate limited request")
        if response.status_code >= 400:
            raise ProviderHTTPError(f"{self.name} returned HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderHTTPError(f"{self.name} returned an unexpected response shape") from exc


class RateLimitError(RuntimeError):
    """Provider returned HTTP 429."""


class ProviderHTTPError(RuntimeError):
    """Provider failed with a retryable or terminal HTTP error."""


def provider_statuses(config: dict[str, Any]) -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []
    for name in PROVIDER_ORDER:
        provider = config.get("providers", {}).get(name, {})
        model = provider.get("model") or PROVIDER_DEFAULTS[name]["model"]
        has_key = bool(provider.get("api_key"))
        statuses.append(
            ProviderStatus(
                name=name,
                model=model,
                api_key_present=has_key,
                status="configured" if has_key else f"missing {ENV_KEYS[name]}",
            )
        )
    return statuses


def build_providers(
    config: dict[str, Any],
    forced_provider: str | None = None,
    model_override: str | None = None,
) -> list[ChatProvider]:
    names = [forced_provider] if forced_provider else PROVIDER_ORDER
    providers: list[ChatProvider] = []
    for name in names:
        if name not in PROVIDER_DEFAULTS:
            raise ValueError(f"Unknown provider: {name}")
        provider_config = config.get("providers", {}).get(name, {})
        api_key = str(provider_config.get("api_key") or "").strip()
        if not api_key:
            continue
        providers.append(
            ChatProvider(
                name=name,
                endpoint=PROVIDER_DEFAULTS[name]["endpoint"],
                model=model_override or provider_config.get("model") or PROVIDER_DEFAULTS[name]["model"],
                api_key=api_key,
            )
        )
    if not providers:
        raise NoProviderConfigured("No configured providers have API keys")
    return providers


def generate_report_markdown(
    user_prompt: str,
    config: dict[str, Any],
    forced_provider: str | None = None,
    model_override: str | None = None,
    attempts_per_provider: int = 3,
) -> tuple[str, str]:
    providers = build_providers(config, forced_provider=forced_provider, model_override=model_override)
    errors: list[str] = []

    for provider in providers:
        for attempt in range(1, attempts_per_provider + 1):
            try:
                return provider.complete(user_prompt), provider.name
            except RateLimitError as exc:
                errors.append(str(exc))
                break
            except (requests.RequestException, ProviderHTTPError, ValueError) as exc:
                errors.append(f"{provider.name} attempt {attempt}: {exc}")
                if attempt < attempts_per_provider:
                    time.sleep(2 ** (attempt - 1))
                continue

    raise ProvidersExhausted(errors)
