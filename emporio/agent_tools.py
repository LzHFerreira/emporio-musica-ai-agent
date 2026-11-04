"""Validate and execute tool batches using application-owned handlers."""

import json
from collections.abc import Callable
from typing import Any

from emporio.agent_schemas import arguments_valid, parse_call

ToolHandler = Callable[[dict[str, Any], str, str], dict[str, Any]]
REF_PREFIXES = {
    "search_catalog": "catalog",
    "list_own_orders": "order",
    "get_own_order_status": "order",
}


def execute_calls(
    calls, messages, sender, model_client, version, handlers, state, provider_content=None
):
    """Execute a model tool batch within the shared four-call ceiling."""
    if not isinstance(calls, list):
        return False
    assistant: dict[str, Any] = {"role": "assistant", "tool_calls": calls}
    if isinstance(provider_content, list):
        assistant["provider_content"] = provider_content
    messages.append(assistant)
    for call in calls:
        if not _execute_one(call, messages, sender, model_client, version, handlers, state):
            return False
    return True


def _execute_one(call, messages, sender, model_client, version, handlers, state):
    parsed = parse_call(call)
    if state["executions"] >= 4 or parsed is None or not arguments_valid(*parsed):
        return False
    name, arguments = parsed
    value = _call_handler(name, arguments, sender, model_client, version, handlers, state)
    _record(call, name, value, messages, state)
    _record_budget(arguments, value, state)
    return True


def _record_budget(arguments, value, state):
    if value.get("outcome") == "found" and arguments.get("max_price_brl"):
        state["evidence"].append({"data": {"budget": arguments["max_price_brl"]}})


def _call_handler(name, arguments, sender, model_client, version, handlers, state):
    state["executions"] += 1
    try:
        before_tool = getattr(model_client, "before_tool", None)
        if callable(before_tool):
            before_tool()
        return handlers[name](arguments, sender, version)
    except Exception:
        return _tool_error()


def _record(call, name, value, messages, state):
    state["operations"].append({"tool": name, "outcome": value.get("outcome", "error")})
    prefix = REF_PREFIXES.get(name)
    for row in value.get("data", []) if prefix else []:
        counts = state.setdefault("refs", {})
        counts[prefix] = counts.get(prefix, 0) + 1
        row["ref"] = f"{prefix}-{counts[prefix]}"
    state["sources"].extend(value.get("sources", []))
    if value.get("outcome") == "found":
        state["evidence"].append(value)
    messages.append(_tool_message(call, name, value))


def _tool_error():
    """Return a bounded source failure without exposing errors or arguments."""
    return {
        "outcome": "error",
        "data": [],
        "sources": [],
        "page": None,
        "pagination_restarted": False,
        "has_more": False,
        "error_category": "source_unavailable",
    }


def _tool_message(call, name, value):
    return {
        "role": "tool",
        "tool_call_id": call.get("id", ""),
        "name": name,
        "content": json.dumps(value, ensure_ascii=False),
    }
