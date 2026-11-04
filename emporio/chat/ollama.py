"""Keyless, bounded client for an explicitly configured local Ollama server."""

import ipaddress
import json
from typing import Any
from urllib.parse import SplitResult, urlsplit

import httpx
from django.conf import settings

from emporio.chat.openrouter import _check_size, _http_client, _post, _request_payload

_URL_SHAPE_ERROR = "OLLAMA_BASE_URL must be a local /v1 URL"
_URL_ERROR = "OLLAMA_BASE_URL must be a local /v1 endpoint on port 11434"
_CREDENTIAL_ERROR = "OLLAMA_BASE_URL must use HTTP(S) without credentials"
_MODEL_ERROR = "OLLAMA_MODEL must identify a local, non-cloud model tag"
_CALL_ERROR = "Ollama returned a malformed tool call"
_FUNCTION_ERROR = "Ollama returned a malformed tool function"


def _require(condition: bool, message: str) -> None:
    """Reject the validated value with one clear message when a rule fails."""
    if not condition:
        raise ValueError(message)


class OllamaClient:
    """Request one local OpenAI-compatible completion without retries."""

    def __init__(self, *, base_url=None, model=None, client: httpx.Client | None = None) -> None:
        """Configure the local endpoint and requested model."""
        endpoint = base_url if base_url is not None else settings.OLLAMA_BASE_URL
        self.model = model if model is not None else settings.OLLAMA_MODEL
        validate_ollama_configuration(endpoint, self.model)
        self.base_url = endpoint.rstrip("/")
        self.client = _unauthenticated_client(client)
        self.request_timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self.returned_model = ""
        self.returned_provider = ""

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Request and validate one assistant message without provider credentials."""
        payload = _request_payload(self.model, messages, tools)
        _check_size(payload)
        message, returned_model, provider = _post(
            self.client,
            self.base_url,
            None,
            payload,
            timeout=self.request_timeout,
            strict_finish=True,
        )
        if returned_model and returned_model != self.model:
            raise ValueError("Ollama returned a model different from the configured model")
        self.returned_model = returned_model
        self.returned_provider = provider or "ollama"
        return _validate_message(message)


def _unauthenticated_client(client: httpx.Client | None) -> httpx.Client:
    """Reuse a caller client only when it carries no provider credentials."""
    if client is not None and ("authorization" in client.headers or client.auth is not None):
        raise ValueError("Ollama client must not carry authentication headers")
    return _http_client(client)


def _validate_message(message: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with reasoning stripped after protocol validation."""
    result = dict(message)
    _require(message.get("role") == "assistant", "Ollama returned a non-assistant message")
    result.pop("reasoning", None)
    identifiers = [_validate_tool_call(call) for call in _message_calls(result)]
    _require(len(set(identifiers)) == len(identifiers), "Ollama returned duplicate tool-call IDs")
    return result


def _message_calls(message: dict[str, Any]) -> list[Any]:
    """Require either usable text content or a well-formed tool-call list."""
    content = message.get("content")
    calls = message.get("tool_calls", [])
    _require(
        content is None or isinstance(content, str),
        "Ollama returned malformed assistant content",
    )
    _require(isinstance(calls, list), "Ollama returned malformed tool calls")
    _require(bool(calls) or _usable_text(content), "Ollama returned an empty assistant message")
    return calls


def _usable_text(content: Any) -> bool:
    """Report whether assistant content holds text."""
    return isinstance(content, str) and bool(content.strip())


def _validate_tool_call(call: Any) -> str:
    """Validate one function tool call and return its identifier."""
    identifier = _tool_identifier(call)
    _tool_arguments(_tool_function(call))
    return identifier


def _tool_function(call: Any) -> Any:
    """Require a function object with a name and return it."""
    function = call.get("function") if isinstance(call, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    _require(isinstance(name, str) and bool(name), _FUNCTION_ERROR)
    return function


def _tool_identifier(call: Any) -> str:
    """Require a function-typed tool call with a nonempty string ID."""
    _require(isinstance(call, dict) and call.get("type") == "function", _CALL_ERROR)
    identifier = call.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(_CALL_ERROR)
    return identifier


def _tool_arguments(function: dict[str, Any]) -> None:
    """Parse supported tool arguments and require a JSON object."""
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Ollama returned malformed tool arguments") from exc
    _require(isinstance(arguments, dict), "Ollama tool arguments must be a JSON object")


def validate_ollama_configuration(base_url: str, model: str) -> None:
    """Allow only an explicit local endpoint and a local model tag."""
    _validate_local_url(base_url)
    _validate_local_model(model)


def _validate_local_model(model: str) -> None:
    """Reject cloud-routed model references, including whitespace-only tags."""
    _require(isinstance(model, str) and bool(model.strip()), _MODEL_ERROR)
    _require(not _cloud_referenced(model), _MODEL_ERROR)


def _cloud_referenced(model: str) -> bool:
    """Recognize URL-like namespaces and Ollama cloud tags."""
    lowered = model.lower()
    namespace = model.split("/", 1)[0]
    remote_path = "://" in model or "ollama.com/" in lowered or ("/" in model and "." in namespace)
    return remote_path or lowered.endswith((":cloud", "-cloud"))


def _validate_local_url(base_url: str) -> None:
    """Require a credential-free local HTTP(S) /v1 endpoint."""
    url, host, port = _url_parts(base_url)
    _require_plain_transport(url)
    _require_v1_endpoint(url, port)
    _require_local_host(host)


def _url_parts(value: str) -> tuple[SplitResult, str, int | None]:
    """Parse the configured endpoint into URL parts, hostname, and port."""
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        port = url.port
    except (TypeError, ValueError) as exc:
        raise ValueError(_URL_SHAPE_ERROR) from exc
    return url, host, port


def _require_plain_transport(url: SplitResult) -> None:
    """Reject non-HTTP schemes and embedded credentials."""
    _require(url.scheme in {"http", "https"}, _CREDENTIAL_ERROR)
    _require(not url.username and not url.password, _CREDENTIAL_ERROR)


def _require_v1_endpoint(url: SplitResult, port: int | None) -> None:
    """Pin the path to the OpenAI-compatible /v1 root on the Ollama port."""
    _require(url.path.rstrip("/") == "/v1", _URL_ERROR)
    _require(not url.query and not url.fragment and port in {None, 11434}, _URL_ERROR)


def _require_local_host(host: str) -> None:
    """Reject public hosts that could route model traffic off the machine."""
    _require(host.lower() == "localhost" or _private_host(host), _URL_ERROR)


def _private_host(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local
