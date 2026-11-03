"""Normalize and compare numeric claims from public result data only."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)")
PRIVATE_KEYS = {
    "page",
    "pages",
    "section",
    "topic",
    "bundle_version",
    "id",
    "sku",
    "product_id",
}


def numbers_supported(text: str, evidence: list[Any]) -> bool:
    """Require every answer number to occur as a complete fact in result data."""
    claimed = _numbers(re.sub(r"^\s*(?:[-*•]\s*)?\d{1,2}[.)](?=\s)", "", text, flags=re.MULTILINE))
    available = _evidence_numbers(evidence)
    return claimed.issubset(available)


def _evidence_numbers(evidence: list[Any]) -> set[Decimal]:
    values: set[Decimal] = set()
    for result in evidence:
        if isinstance(result, dict):
            _collect(result.get("data", result), values)
    return values


def _collect(value: Any, output: set[Decimal], key: str = "") -> None:
    if key in PRIVATE_KEYS:
        return
    if isinstance(value, dict):
        _collect_mapping(value, output)
    elif isinstance(value, (list, tuple)):
        _collect_items(value, output)
    else:
        _collect_scalar(value, output)


def _collect_mapping(value: dict[Any, Any], output: set[Decimal]) -> None:
    for key, child in value.items():
        _collect(child, output, str(key))


def _collect_items(value: list[Any] | tuple[Any, ...], output: set[Decimal]) -> None:
    for child in value:
        _collect(child, output)


def _collect_scalar(value: Any, output: set[Decimal]) -> None:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        output.update(_numbers(str(value)))


def _numbers(text: str) -> set[Decimal]:
    values = set()
    for match in NUMBER.finditer(text):
        number = _decimal(match.group())
        if number is not None:
            values.add(number)
    return values


def _decimal(value: str) -> Decimal | None:
    normalized = _separator_normalized(value)
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _separator_normalized(value: str) -> str:
    if "." in value and "," in value:
        return _normalize_mixed(value)
    if "," in value:
        return _normalize_comma(value)
    if "." in value:
        return _normalize_dot(value)
    return value


def _normalize_mixed(value: str) -> str:
    if value.rfind(",") > value.rfind("."):
        return value.replace(".", "").replace(",", ".")
    return value.replace(",", "")


def _normalize_comma(value: str) -> str:
    head, tail = value.rsplit(",", 1)
    if len(tail) <= 2:
        return f"{head.replace(',', '')}.{tail}"
    return value.replace(",", "")


def _normalize_dot(value: str) -> str:
    head, tail = value.rsplit(".", 1)
    return head.replace(".", "") + tail if len(tail) == 3 else value
