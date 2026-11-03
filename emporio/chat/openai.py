"""Direct OpenAI Responses and explicit Chat Completions adapters."""

from typing import Any

from django.conf import settings

from emporio.chat.model_http import post_with_timeout
from emporio.chat.openai_responses import parse_response, request_payload
from emporio.chat.openrouter import _check_size
from emporio.chat.provider_http import provider_http_client

_RESPONSES_URL = "https://api.openai.com/v1/responses"
_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_CHAT_UNSUPPORTED = {"gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra"}
_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}


class OpenAIClient:
    """Use OpenAI's stateless Responses API or explicit compatible chat mode."""

    def __init__(
        self, *, api_key=None, model=None, api_mode=None, reasoning_effort=None, client=None
    ) -> None:
        """Configure the selected OpenAI endpoint, model, and bounded HTTP client."""
        (
            self.api_key,
            self.model,
            self.api_mode,
            self.reasoning_effort,
        ) = _configuration(api_key, model, api_mode, reasoning_effort)
        self.client = provider_http_client(client)
        self.request_timeout = 60.0
        self.returned_model = ""
        self.returned_provider = ""

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Send one bounded request and return the shared assistant-message shape."""
        if self.api_mode == "responses":
            return self._responses(messages, tools)
        return self._chat(messages, tools)

    def _responses(self, messages, tools):
        payload = request_payload(self.model, messages, tools, self.reasoning_effort)
        return _send(self, _RESPONSES_URL, payload, parse_response)

    def _chat(self, messages, tools):
        payload = {
            "model": self.model,
            "max_completion_tokens": 1024,
            "messages": _chat_messages(messages),
            "tools": tools,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        return _send(self, _CHAT_URL, payload, _chat_message)


def _chat_messages(messages):
    return [
        {key: value for key, value in message.items() if key != "provider_content"}
        for message in messages
    ]


def _send(client, url, payload, parse):
    _check_size(payload)
    response = post_with_timeout(
        client.client,
        url,
        headers={"Authorization": f"Bearer {client.api_key}"},
        payload=payload,
        timeout=client.request_timeout,
    )
    response.raise_for_status()
    body = response.json()
    message = parse(body)
    client.returned_model = _model(body)
    client.returned_provider = "openai"
    return message


def _chat_message(body: Any) -> dict[str, Any]:
    message = _chat_choice(body)
    if message is None:
        raise ValueError("OpenAI returned a malformed assistant message")
    if not _valid_chat_content(message):
        raise ValueError("OpenAI returned a malformed assistant message")
    if _empty_chat_message(message):
        raise ValueError("OpenAI returned an empty assistant message")
    return message


def _chat_choice(body: Any) -> dict[str, Any] | None:
    choice = _first_choice(body)
    if choice is None:
        raise ValueError("OpenAI returned an incomplete or malformed chat result")
    if choice.get("finish_reason") not in {"stop", "tool_calls"}:
        raise ValueError("OpenAI returned an incomplete or malformed chat result")
    return _assistant_message(choice.get("message"))


def _first_choice(body: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return None


def _assistant_message(message: Any) -> dict[str, Any] | None:
    if isinstance(message, dict) and message.get("role") == "assistant":
        return message
    return None


def _valid_chat_content(message: dict[str, Any]) -> bool:
    content, calls = message.get("content"), message.get("tool_calls", [])
    return (content is None or isinstance(content, str)) and isinstance(calls, list)


def _empty_chat_message(message: dict[str, Any]) -> bool:
    content, calls = message.get("content"), message.get("tool_calls", [])
    if isinstance(content, str) and content.strip():
        return False
    return not calls


def _model(body):
    value = body.get("model") if isinstance(body, dict) else None
    return value if isinstance(value, str) else ""


def _configuration(api_key, model, api_mode, reasoning_effort):
    key = _resolve(api_key, settings.OPENAI_API_KEY)
    selected_model = _resolve(model, settings.OPENAI_MODEL)
    selected_mode = _resolve(api_mode, settings.OPENAI_API_MODE)
    selected_effort = _resolve(reasoning_effort, settings.OPENAI_REASONING_EFFORT)
    _validate_key(key)
    _validate_model(selected_model)
    selected_effort = _validate_mode(selected_mode, selected_model, selected_effort)
    return key, selected_model, selected_mode, selected_effort


def _resolve(value, fallback):
    return value if value is not None else fallback


def _validate_key(key):
    if not key:
        raise ValueError("Set OPENAI_API_KEY before using OpenAI")


def _validate_model(model):
    if not model or len(model) > 160:
        raise ValueError("Set a valid OPENAI_MODEL before using OpenAI")


def _validate_mode(mode, model, effort):
    if mode not in {"responses", "chat_completions"}:
        raise ValueError("OPENAI_API_MODE must be responses or chat_completions")
    _validate_effort(effort)
    return _validate_chat_mode(mode, model, effort)


def _validate_effort(effort):
    if effort and effort not in _EFFORTS:
        raise ValueError("OPENAI_REASONING_EFFORT is not supported")


def _validate_chat_mode(mode, model, effort):
    if mode != "chat_completions":
        return effort
    if model in _CHAT_UNSUPPORTED:
        raise ValueError("This OpenAI model requires OPENAI_API_MODE=responses for tool calls")
    if model == "gpt-6-luna":
        return _luna_effort(effort)
    return effort


def _luna_effort(effort):
    if effort not in {"", "none"}:
        raise ValueError("GPT-6 Luna Chat Completions tool calls require reasoning effort none")
    return "none"
