"""HTTP adapter for Anthropic Messages and native tool-use blocks."""

from typing import Any

from django.conf import settings

from emporio.chat.anthropic_protocol import assistant_response, messages_payload, tool_schema
from emporio.chat.model_http import post_with_timeout
from emporio.chat.openrouter import _check_size
from emporio.chat.provider_http import provider_http_client

_URL = "https://api.anthropic.com/v1/messages"
_VERSION = "2026-10-21"


class AnthropicClient:
    """Request a bounded Anthropic message and normalize its tool-use response."""

    def __init__(self, *, api_key=None, model=None, client=None) -> None:
        """Configure the explicit Anthropic key and model."""
        self.api_key, self.model = _credentials(api_key, model)
        self.client = provider_http_client(client)
        self.request_timeout = 60.0
        self.returned_model = ""
        self.returned_provider = ""

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Translate the shared chat protocol, call Messages, and normalize one result."""
        system, translated = messages_payload(messages)
        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": translated,
            "tools": [tool_schema(tool) for tool in tools],
        }
        _check_size(payload)
        body = _request(self, payload)
        result = assistant_response(body)
        self.returned_model = _returned_model(body)
        self.returned_provider = "anthropic"
        return result


def _credentials(api_key, model):
    key = _resolve(api_key, settings.ANTHROPIC_API_KEY)
    selected_model = _resolve(model, settings.ANTHROPIC_MODEL)
    _require_key(key)
    _require_model(selected_model)
    return key, selected_model


def _resolve(value, fallback):
    return value if value is not None else fallback


def _require_key(key):
    if not key:
        raise ValueError("Set ANTHROPIC_API_KEY before using Anthropic")


def _require_model(model):
    if not model or len(model) > 160:
        raise ValueError("Set a valid ANTHROPIC_MODEL before using Anthropic")


def _request(client, payload: dict[str, object]) -> dict[str, Any]:
    response = post_with_timeout(
        client.client,
        _URL,
        headers={"x-api-key": client.api_key, "anthropic-version": _VERSION},
        payload=payload,
        timeout=client.request_timeout,
    )
    response.raise_for_status()
    return response.json()


def _returned_model(body: dict[str, Any]) -> str:
    value = body.get("model")
    return value if isinstance(value, str) else ""
