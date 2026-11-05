"""Provide Gemma with a private, validated terminal-reply function."""

import json
from copy import deepcopy
from typing import Any

_NAME = "respond_to_customer"
_INSTRUCTION = (
    "For customer replies, use respond_to_customer only after checking all needed facts with "
    "the business tools. Put the final answer in a separate call. Never batch this reply call "
    "with any business-tool call. Use an empty catalog query only for general browsing. If a "
    "specific product reference is missing or ambiguous, ask the customer to clarify rather "
    "than repeating an empty or ambiguous search. Put catalog refs in facts, never in the text. "
    "Never write prices, stock or order status in text; list catalog-N or order-N refs in facts "
    "and the application writes them. Do not send final prose outside this function."
)
_TOOL = {
    "type": "function",
    "function": {
        "name": _NAME,
        "description": "Return one final customer response after the required facts are verified.",
        "parameters": {
            "type": "object",
            "properties": {
                "outcome": {
                    "type": "string",
                    "enum": ["answer", "clarification", "handoff", "out_of_scope"],
                },
                "text": {"type": "string", "minLength": 1, "maxLength": 2000},
                "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "reason": {
                    "type": ["string", "null"],
                    "enum": [
                        None,
                        "customer_request",
                        "verification_failed",
                        "unsupported",
                        "other",
                    ],
                },
            },
            "required": ["outcome", "text", "reason"],
            "additionalProperties": False,
        },
    },
}


def gemma_request(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Copy request inputs, append the private terminal tool, and add its instruction."""
    return _with_instruction(messages), [*_gemma_tools(tools), deepcopy(_TOOL)]


def _gemma_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = []
    for tool in tools:
        if tool.get("function", {}).get("name") == "search_catalog":
            copied.append(_search_schema(tool))
        else:
            copied.append(tool)
    return copied


def _search_schema(tool: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(tool)
    function = copied["function"]
    function["description"] = (
        "Search using a customer-provided product name, brand, or model. Use an empty query "
        "only for general browsing; ask the customer to clarify a missing specific reference."
    )
    parameters = function["parameters"]
    parameters.setdefault("required", []).append("query")
    parameters["properties"]["query"].pop("default", None)
    parameters["properties"]["query"]["description"] = (
        "Product name, brand, or model from the customer. Empty string is for general browsing."
    )
    return copied


def _with_instruction(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = [dict(message) for message in messages]
    for index, message in enumerate(copied):
        if message.get("role") == "system":
            copied[index] = {**message, "content": _system_content(message)}
            return copied
    return [{"role": "system", "content": _INSTRUCTION}, *copied]


def _system_content(message: dict[str, Any]) -> str:
    existing = message.get("content")
    prefix = existing if isinstance(existing, str) else ""
    return f"{prefix}\n\n{_INSTRUCTION}" if prefix else _INSTRUCTION


def normalize_reply(message: dict[str, Any]) -> dict[str, Any]:
    """Convert one valid private function call into the agent's terminal JSON text."""
    calls = message.get("tool_calls", [])
    controls = [call for call in calls if _is_reply_call(call)]
    if not controls:
        return message
    _validate_reply_batch(controls, calls)
    content = _terminal_content(controls[0])
    return {"role": "assistant", "content": content, "tool_calls": []}


def validate_search_calls(message: dict[str, Any]) -> None:
    """Require a string query for each Gemma catalog call; empty browse remains valid."""
    for call in message.get("tool_calls", []):
        _validate_search_call(call)


def _validate_search_call(call: Any) -> None:
    function = call.get("function") if isinstance(call, dict) else None
    if not isinstance(function, dict) or function.get("name") != "search_catalog":
        return
    arguments = _function_arguments(function)
    if not isinstance(arguments.get("query"), str):
        raise ValueError("Gemma search_catalog call requires a string query")


def _function_arguments(function: dict[str, Any]) -> dict[str, Any]:
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Gemma returned malformed catalog arguments") from exc
    return arguments if isinstance(arguments, dict) else {}


def _validate_reply_batch(controls, calls):
    if len(controls) != 1:
        raise ValueError("Gemma repeated its terminal reply function")
    if len(calls) != 1:
        raise ValueError("Gemma mixed terminal reply with a business tool")


def _is_reply_call(call: Any) -> bool:
    function = call.get("function") if isinstance(call, dict) else None
    return isinstance(function, dict) and function.get("name") == _NAME


def _terminal_content(call: dict[str, Any]) -> str:
    function = call.get("function")
    if not isinstance(function, dict):
        raise ValueError("Gemma returned malformed terminal-reply arguments")
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Gemma returned malformed terminal-reply arguments") from exc
    if not isinstance(arguments, dict):
        raise ValueError("Gemma returned malformed terminal-reply arguments")
    content = json.dumps(arguments, ensure_ascii=False)
    return content
