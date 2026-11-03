"""Translate shared messages to Anthropic's native block protocol."""

import json
from typing import Any


def messages_payload(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Map shared messages into system text and Messages API entries."""
    system: list[str] = []
    translated: list[dict[str, Any]] = []
    for item in messages:
        _append_message(item, system, translated)
    return "\n\n".join(system), translated


def _append_message(
    item: dict[str, Any], system: list[str], translated: list[dict[str, Any]]
) -> None:
    role = item.get("role")
    action = _MESSAGE_HANDLERS.get(role) if isinstance(role, str) else None
    if action:
        action(item, system, translated)


def _append_system(item, system, translated):
    del translated
    system.append(str(item.get("content") or ""))


def _append_tool(item, system, translated):
    del system
    _append_tool_result(translated, item)


def _append_assistant_message(item, system, translated):
    del system
    _append_assistant(item, translated)


def _append_user(item, system, translated):
    del system
    translated.append({"role": "user", "content": str(item.get("content") or "")})


_MESSAGE_HANDLERS = {
    "system": _append_system,
    "tool": _append_tool,
    "assistant": _append_assistant_message,
    "user": _append_user,
}


def _append_assistant(item: dict[str, Any], translated: list[dict[str, Any]]) -> None:
    native = item.get("provider_content")
    if native is not None:
        translated.append({"role": "assistant", "content": native})
    elif item.get("tool_calls"):
        translated.append(
            {"role": "assistant", "content": [_native_call(call) for call in item["tool_calls"]]}
        )
    else:
        translated.append({"role": "assistant", "content": str(item.get("content") or "")})


def _append_tool_result(messages: list[dict[str, Any]], item: dict[str, Any]) -> None:
    block = {
        "type": "tool_result",
        "tool_use_id": item.get("tool_call_id", ""),
        "content": item.get("content", ""),
    }
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"].append(block)
    else:
        messages.append({"role": "user", "content": [block]})


def _native_call(call: dict[str, Any]) -> dict[str, Any]:
    function = call["function"]
    return {
        "type": "tool_use",
        "id": call["id"],
        "name": function["name"],
        "input": json.loads(function["arguments"]),
    }


def tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a shared function schema to the Messages API tool shape."""
    function = tool["function"]
    return {
        "name": function["name"],
        "description": function["description"],
        "input_schema": function["parameters"],
    }


def assistant_response(body: Any) -> dict[str, Any]:
    """Validate and normalize a Messages API response while preserving native blocks."""
    blocks = _response_blocks(body)
    text: list[str] = []
    calls: list[dict[str, Any]] = []
    for block in blocks:
        _collect_block(block, text, calls)
    if not calls and not "".join(text).strip():
        raise ValueError("Anthropic returned an empty assistant message")
    return {
        "role": "assistant",
        "content": "".join(text) or None,
        "tool_calls": calls,
        "provider_content": blocks,
    }


def _response_blocks(body: Any) -> list[Any]:
    blocks = body.get("content") if isinstance(body, dict) else None
    if not isinstance(blocks, list) or body.get("stop_reason") not in {"end_turn", "tool_use"}:
        raise ValueError("Anthropic returned an incomplete or malformed response")
    if len(json.dumps(blocks, ensure_ascii=False).encode("utf-8")) > 32 * 1024:
        raise ValueError("Anthropic response exceeds configured byte bound")
    return blocks


def _collect_block(block: Any, text: list[str], calls: list[dict[str, Any]]) -> None:
    if not isinstance(block, dict):
        raise ValueError("Anthropic returned malformed content blocks")
    block_type = block.get("type")
    action = _BLOCK_HANDLERS.get(block_type) if isinstance(block_type, str) else None
    if action:
        action(block, text, calls)
    elif block_type not in {"thinking", "redacted_thinking"}:
        raise ValueError("Anthropic returned an unsupported content block")


def _append_text(block, text, calls):
    del calls
    value = block.get("text")
    if isinstance(value, str):
        text.append(value)


def _append_call(block, text, calls):
    del text
    calls.append(_tool_call(block))


_BLOCK_HANDLERS = {"text": _append_text, "tool_use": _append_call}


def _tool_call(block: dict[str, Any]) -> dict[str, Any]:
    identifier, name, arguments = block.get("id"), block.get("name"), block.get("input")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Anthropic returned malformed tool use")
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise ValueError("Anthropic returned malformed tool use")
    return {
        "id": identifier,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }
