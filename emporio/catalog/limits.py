"""Bound serialized public catalog results while preserving decision facts."""

import json
from typing import Any

MAX_RESULT_BYTES = 12 * 1024


def fit_result(result: dict[str, Any]) -> dict[str, Any]:
    """Trim optional description/specification text to the result-size ceiling."""
    if _within_limit(result):
        return result
    data = result["data"]
    _trim_descriptions(data, 120)
    _trim_spec_values(data, 40)
    if _within_limit(result):
        return result
    _remove_spec_fields(data)
    _trim_descriptions(data, 40)
    if _within_limit(result):
        return result
    _trim_descriptions(data, 0)
    if _within_limit(result):
        return result
    return _bounded_error()


def _within_limit(result: dict[str, Any]) -> bool:
    """Measure compact UTF-8 JSON bytes as sent to the model interface."""
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return len(encoded) <= MAX_RESULT_BYTES


def _trim_descriptions(data: list[dict[str, Any]], limit: int) -> None:
    """Shorten optional product descriptions and record each truncation."""
    for item in data:
        value = item["description"]
        if len(value) > limit:
            item["description"] = value[:limit]
            _mark(item, "description")


def _trim_spec_values(data: list[dict[str, Any]], limit: int) -> None:
    """Shorten optional specification values and record each truncation."""
    for item in data:
        for key, value in item["specs"].items():
            if len(value) > limit:
                item["specs"][key] = value[:limit]
                _mark(item, f"specs.{key}")


def _remove_spec_fields(data: list[dict[str, Any]]) -> None:
    """Remove optional specification fields when value trimming is insufficient."""
    for item in data:
        for key in list(item["specs"]):
            del item["specs"][key]
            _mark(item, f"specs.{key}")


def _mark(item: dict[str, Any], field: str) -> None:
    """Add a unique marker for an omitted or shortened public field."""
    if field not in item["truncated_fields"]:
        item["truncated_fields"].append(field)


def _bounded_error() -> dict[str, Any]:
    """Return the standard envelope when required facts alone exceed the cap."""
    return {
        "outcome": "error",
        "data": [],
        "sources": [],
        "page": None,
        "pagination_restarted": False,
        "has_more": False,
        "error_category": "result_too_large",
    }
