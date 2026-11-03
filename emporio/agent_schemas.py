"""Load and validate the four allowlisted model tool schemas."""

import json
import re
from pathlib import Path
from typing import Any

TOOL_SCHEMAS = json.loads(
    (Path(__file__).resolve().parents[1] / "docs/tool-schemas.json").read_text(encoding="utf-8")
)


def parse_call(call: Any) -> tuple[str, dict[str, Any]] | None:
    """Parse one OpenAI function call without trusting model-provided structure."""
    if not isinstance(call, dict) or call.get("type") != "function":
        return None
    return _function_arguments(call.get("function"))


def _function_arguments(function: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(function, dict):
        return None
    name, raw = function.get("name"), function.get("arguments")
    if not isinstance(name, str) or not _registered_name(name):
        return None
    arguments = _decode_object(raw)
    if arguments is None:
        return None
    return name, _coerce_budget(arguments)


def _coerce_budget(arguments: dict[str, Any]) -> dict[str, Any]:
    if type(arguments.get("max_price_brl")) is int:
        arguments["max_price_brl"] = str(arguments["max_price_brl"])
    return arguments


def _registered_name(name: Any) -> bool:
    return isinstance(name, str) and name in _tool_names()


def _decode_object(raw: Any) -> dict[str, Any] | None:
    try:
        arguments = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return arguments if isinstance(arguments, dict) else None


def _tool_names() -> set[str]:
    return {item["function"]["name"] for item in TOOL_SCHEMAS}


def arguments_valid(name: str, value: dict[str, Any]) -> bool:
    """Validate registered properties, required keys, and primitive values."""
    schema = _tool_schema(name)
    if schema is None or not _keys_valid(schema, value):
        return False
    return all(
        _valid_value(value[key], rule) for key, rule in schema["properties"].items() if key in value
    )


def _tool_schema(name: str) -> dict[str, Any] | None:
    for item in TOOL_SCHEMAS:
        if item["function"]["name"] == name:
            return item["function"]["parameters"]
    return None


def _keys_valid(schema: dict[str, Any], value: dict[str, Any]) -> bool:
    return not (
        schema.get("additionalProperties") is False and set(value) - set(schema["properties"])
    ) and not (set(schema.get("required", [])) - set(value))


def _valid_value(value: Any, rule: dict[str, Any]) -> bool:
    kinds = rule.get("type")
    types = kinds if isinstance(kinds, list) else [kinds]
    return _type_valid(value, types) and _constraints_valid(value, rule)


def _type_valid(value: Any, types: list[str | None]) -> bool:
    return any(_matches_type(value, kind) for kind in types)


def _constraints_valid(value: Any, rule: dict[str, Any]) -> bool:
    return _enum_valid(value, rule) and _bound_valid(value, rule)


def _enum_valid(value: Any, rule: dict[str, Any]) -> bool:
    return (
        "enum" not in rule
        or isinstance(value, (str, int, bool, type(None)))
        and value in rule["enum"]
    )


def _bound_valid(value: Any, rule: dict[str, Any]) -> bool:
    if isinstance(value, str):
        return _string_valid(value, rule)
    if type(value) is int:
        return rule.get("minimum", value) <= value <= rule.get("maximum", value)
    return True


def _string_valid(value: str, rule: dict[str, Any]) -> bool:
    size_ok = rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", 10**9)
    pattern = rule.get("pattern")
    return size_ok and (pattern is None or re.fullmatch(pattern, value) is not None)


def _matches_type(value: Any, kind: str | None) -> bool:
    if kind is None:
        return True
    return {
        "string": lambda: isinstance(value, str),
        "integer": lambda: type(value) is int,
        "boolean": lambda: type(value) is bool,
        "object": lambda: isinstance(value, dict),
        "null": lambda: value is None,
    }.get(kind, lambda: True)()
