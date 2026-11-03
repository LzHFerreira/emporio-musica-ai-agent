"""OpenRouter-compatible JSON tool-call client with bounded request size."""

import json
from typing import Any

import httpx
from django.conf import settings

from emporio.chat.model_http import post_with_timeout

MAX_CONTEXT_BYTES = 32 * 1024


class OpenRouterClient:
    """Request one model response without implicit retries or model fallback."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        client: httpx.Client | None = None,
    ) -> None:
        """Configure the explicit model, API key, timeout, and injectable client."""
        self.api_key = _choose(api_key, settings.OPENROUTER_API_KEY)
        self.model = _choose(model, settings.OPENROUTER_MODEL)
        self.base_url = base_url.rstrip("/")
        self.client = _http_client(client)
        self.request_timeout = 60.0
        self.returned_model = ""
        self.returned_provider = ""

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """POST one bounded completion and return only its assistant message."""
        payload = _request_payload(self.model, messages, tools)
        _check_size(payload)
        message, self.returned_model, self.returned_provider = _post(
            self.client, self.base_url, self.api_key, payload, timeout=self.request_timeout
        )
        return message


def _choose(value, fallback):
    return fallback if value is None else value


def _http_client(client):
    if client is not None and (
        client.auth is not None
        or {"authorization", "x-api-key", "api-key"}.intersection(client.headers)
    ):
        raise ValueError("HTTP client must not carry provider credentials")
    return client if client is not None else httpx.Client(timeout=60.0)


def _request_payload(model, messages, tools):
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 1024,
        "messages": messages,
        "tools": tools,
    }


def _check_size(payload):
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ValueError("model context exceeds configured byte bound")


def _post(client, base_url, api_key, payload, *, timeout=60.0, strict_finish=False):
    response = post_with_timeout(
        client,
        f"{base_url}/chat/completions",
        headers=_authorization(api_key),
        payload=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    _verify_finish_reason(_first_choice(body), strict_finish)
    return _assistant_message(body), _returned(body, "model"), _returned(body, "provider")


def _authorization(api_key):
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _verify_finish_reason(choice, strict_finish) -> None:
    """Reject truncation always and, for local providers, unknown finish reasons."""
    reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    if reason == "length" or (strict_finish and reason not in {"stop", "tool_calls"}):
        raise ValueError("model response is incomplete or has no supported finish reason")


def _assistant_message(body):
    message = _first_message(_first_choice(body))
    if not isinstance(message, dict):
        raise ValueError("model response has no assistant message")
    return message


def _first_choice(body):
    choices = body.get("choices") if isinstance(body, dict) else None
    return choices[0] if isinstance(choices, list) and choices else None


def _first_message(choice):
    return choice.get("message") if isinstance(choice, dict) else None


def _returned(body, key):
    value = body.get(key) if isinstance(body, dict) else None
    return value if isinstance(value, str) else ""
