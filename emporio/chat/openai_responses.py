"""Translate the agent's shared message protocol to stateless Responses items."""

import json
from typing import Any


def request_payload(model, messages, tools, reasoning_effort):
    """Build a stateless Responses request, replaying bounded native output items."""
    instructions, items = [], []
    for message in messages:
        _append_input(message, instructions, items)
    payload = {
        "model": model,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "max_output_tokens": 1024,
        "instructions": "\n\n".join(instructions),
        "input": items,
        "tools": [_responses_tool(tool) for tool in tools],
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


def parse_response(body: Any) -> dict[str, Any]:
    """Normalize completed Responses output and retain native items for tool replay."""
    output = _completed_output(body)
    text: list[str] = []
    calls: list[dict[str, Any]] = []
    for item in output:
        _collect_output(item, text, calls)
    _check_response_size(output)
    if _empty_response(text, calls):
        raise ValueError("OpenAI returned an empty assistant message")
    return {
        "role": "assistant",
        "content": "".join(text) or None,
        "tool_calls": calls,
        "provider_content": output,
    }


def _append_input(message, instructions, items):
    role = message.get("role")
    action = _INPUT_HANDLERS.get(role) if isinstance(role, str) else None
    if action:
        action(message, instructions, items)


def _append_system(message, instructions, items):
    del items
    instructions.append(str(message.get("content") or ""))


def _append_user(message, instructions, items):
    del instructions
    items.append({"role": "user", "content": str(message.get("content") or "")})


def _append_assistant(message, instructions, items):
    del instructions
    native = message.get("provider_content")
    if isinstance(native, list):
        items.extend(native)
    elif message.get("tool_calls"):
        items.extend(_function_call(call) for call in message["tool_calls"])
    else:
        items.append({"role": "assistant", "content": str(message.get("content") or "")})


def _append_tool(message, instructions, items):
    del instructions
    items.append(
        {
            "type": "function_call_output",
            "call_id": message.get("tool_call_id", ""),
            "output": message.get("content", ""),
        }
    )


_INPUT_HANDLERS = {
    "system": _append_system,
    "user": _append_user,
    "assistant": _append_assistant,
    "tool": _append_tool,
}


def _completed_output(body):
    if not isinstance(body, dict) or body.get("status") != "completed":
        raise ValueError("OpenAI returned an incomplete or malformed Responses result")
    output = body.get("output")
    if not isinstance(output, list) or not output:
        raise ValueError("OpenAI returned an empty Responses result")
    return output


def _collect_output(item, text, calls):
    if not isinstance(item, dict):
        raise ValueError("OpenAI returned malformed Responses output")
    item_type = item.get("type")
    action = _OUTPUT_HANDLERS.get(item_type) if isinstance(item_type, str) else None
    if action:
        action(item, text, calls)
    elif item.get("type") != "reasoning":
        raise ValueError("OpenAI returned an unsupported Responses output item")


def _collect_message(item, text, calls):
    del calls
    text.extend(
        block.get("text", "")
        for block in item.get("content", [])
        if isinstance(block, dict) and block.get("type") == "output_text"
    )


def _collect_call(item, text, calls):
    del text
    calls.append(_responses_call(item))


_OUTPUT_HANDLERS = {"message": _collect_message, "function_call": _collect_call}


def _check_response_size(output):
    if len(json.dumps(output, ensure_ascii=False).encode("utf-8")) > 32 * 1024:
        raise ValueError("OpenAI response exceeds configured byte bound")


def _empty_response(text, calls):
    return not calls and not "".join(text).strip()


def _function_call(call):
    function = call["function"]
    return {
        "type": "function_call",
        "call_id": call["id"],
        "name": function["name"],
        "arguments": function["arguments"],
    }


def _responses_tool(tool):
    function = tool["function"]
    return {
        "type": "function",
        "name": function["name"],
        "description": function.get("description", ""),
        "parameters": function["parameters"],
    }


def _responses_call(item):
    identifier, name, arguments = item.get("call_id"), item.get("name"), item.get("arguments")
    try:
        parsed = json.loads(arguments)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("OpenAI returned malformed function arguments") from exc
    if not _valid_responses_call(identifier, name, parsed):
        raise ValueError("OpenAI returned malformed function call")
    return {
        "id": identifier,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(parsed, ensure_ascii=False)},
    }


def _valid_responses_call(identifier, name, parsed):
    return (
        isinstance(identifier, str)
        and bool(identifier)
        and isinstance(name, str)
        and isinstance(parsed, dict)
    )
