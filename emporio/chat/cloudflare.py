"""OpenAI-compatible Cloudflare Workers AI client for the verified Gemma route."""

import json
import re
from typing import Any

from django.conf import settings

from emporio.chat.cloudflare_reply import gemma_request, normalize_reply, validate_search_calls
from emporio.chat.model_http import post_with_timeout
from emporio.chat.openrouter import _check_size
from emporio.chat.provider_http import provider_http_client

_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{}/ai/v1"


class CloudflareClient:
    """Request one bounded tool-capable completion from an explicit account route."""

    def __init__(self, *, account_id=None, api_key=None, model=None, client=None) -> None:
        """Configure account credentials, the requested model, and an optional test client."""
        self.account_id = account_id if account_id is not None else settings.CLOUDFLARE_ACCOUNT_ID
        self.api_key = api_key if api_key is not None else settings.CLOUDFLARE_API_KEY
        self.model = model if model is not None else settings.CLOUDFLARE_MODEL
        _validate_config(self.account_id, self.api_key, self.model)
        self.base_url = _BASE_URL.format(self.account_id)
        self.client = provider_http_client(client)
        self.request_timeout = 60.0
        self.returned_model = ""
        self.returned_provider = ""

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Post one context-bounded completion and return its assistant message."""
        message, model = _request(self, messages, tools)
        self.returned_model = model
        self.returned_provider = "cloudflare"
        return message


def _request(client, messages, tools):
    messages, tools = gemma_request(messages, tools)
    payload = _request_payload(client.model, messages, tools)
    body = _post(client, payload)
    message = _assistant(body)
    validate_search_calls(message)
    message = normalize_reply(message)
    return message, _text(body.get("model"))


def _request_payload(model, messages, tools) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "temperature": 0,
        "max_tokens": 1024,
        "messages": messages,
        "tools": tools,
    }
    if model == "@cf/google/gemma-4-26b-a4b-it":
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    payload["tool_choice"] = "required"
    _check_size(payload)
    return payload


def _post(client, payload: dict[str, object], retry: bool = True) -> dict[str, Any]:
    response = post_with_timeout(
        client.client,
        f"{client.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {client.api_key}"},
        payload=payload,
        timeout=client.request_timeout,
    )
    if retry and _is_malformed_tool_call(response):
        return _post(client, payload, retry=False)
    response.raise_for_status()
    return response.json()


def _is_malformed_tool_call(response) -> bool:
    if response.status_code != 400:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    errors = body.get("errors") if isinstance(body, dict) else None
    if not isinstance(errors, list):
        return False
    return any(isinstance(error, dict) and error.get("code") == 3030 for error in errors)


def _validate_config(account_id: str, api_key: str, model: str) -> None:
    _validate_account(account_id)
    _validate_key(api_key)
    _validate_model(model)


def _validate_account(account_id: str) -> None:
    if not isinstance(account_id, str) or not _ACCOUNT_ID.fullmatch(account_id):
        raise ValueError("Set a valid CLOUDFLARE_ACCOUNT_ID before using Cloudflare")


def _validate_key(api_key: str) -> None:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Set CLOUDFLARE_API_KEY before using Cloudflare")


def _validate_model(model: str) -> None:
    if not isinstance(model, str) or not model.strip() or len(model) > 160:
        raise ValueError("Set a valid CLOUDFLARE_MODEL before using Cloudflare")


def _assistant(body: Any) -> dict[str, Any]:
    message, reason = _choice_message(body)
    if reason == "length":
        raise ValueError("Cloudflare returned an incomplete or malformed response")
    _validate_message(message)
    _validate_tool_calls(message.get("tool_calls", []))
    return message


def _choice_message(body: Any) -> tuple[dict[str, Any], Any]:
    choice = _first_choice(body)
    if choice is None:
        raise ValueError("Cloudflare returned an incomplete or malformed response")
    return _assistant_choice(choice)


def _first_choice(body: Any) -> dict[str, Any] | None:
    choices = body.get("choices") if isinstance(body, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return None


def _assistant_choice(choice: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("Cloudflare returned an incomplete or malformed response")
    return message, choice.get("finish_reason")


def _validate_message(message: dict[str, Any]) -> None:
    if len(json.dumps(message, ensure_ascii=False).encode("utf-8")) > 32 * 1024:
        raise ValueError("Cloudflare response exceeds configured byte bound")
    content, calls = message.get("content"), message.get("tool_calls", [])
    if not _valid_message_fields(content, calls):
        raise ValueError("Cloudflare returned a malformed assistant message")
    if not _has_content(content, calls):
        raise ValueError("Cloudflare returned an empty assistant message")


def _valid_message_fields(content: Any, calls: Any) -> bool:
    return (content is None or isinstance(content, str)) and isinstance(calls, list)


def _has_content(content: Any, calls: list[Any]) -> bool:
    return bool(calls) or isinstance(content, str) and bool(content.strip())


def _validate_tool_calls(calls: list[Any]) -> None:
    for call in calls:
        _validate_tool_call(call)


def _validate_tool_call(call: Any) -> None:
    function = call.get("function") if isinstance(call, dict) else None
    arguments = _tool_arguments(function)
    if not isinstance(arguments, dict):
        raise ValueError("Cloudflare returned malformed tool arguments")


def _tool_arguments(function: Any) -> Any:
    if not isinstance(function, dict):
        raise ValueError("Cloudflare returned malformed tool arguments")
    try:
        return json.loads(function.get("arguments", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Cloudflare returned malformed tool arguments") from exc


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""
