"""Shared strict parsers for the fixed source CSV schemas."""

import json
from datetime import datetime

from emporio.catalog.pricing import cents, percentage_basis_points
from emporio.sources.read import SourceImportError

SPEC_KEYS = {
    "top",
    "back_sides",
    "neck",
    "strings",
    "scale",
    "electronics",
    "color",
    "body",
    "shells",
    "pieces",
    "hardware",
    "keys",
    "type",
    "polyphony",
}
__all__ = ["integer", "money", "percent", "source_date", "specs_value", "flag", "required"]


def integer(value: str, field: str, minimum: int = 0) -> int:
    """Parse an integer field without accepting signs, decimals, or blanks."""
    if not value.isascii() or not value.isdecimal() or int(value) < minimum:
        raise SourceImportError(f"invalid {field}")
    return int(value)


def money(value: str, field: str) -> int:
    """Convert validated source currency to integer cents."""
    try:
        return cents(value)
    except ValueError as error:
        raise SourceImportError(f"invalid {field}") from error


def percent(value: str) -> int:
    """Convert a source percentage to bounded basis points."""
    try:
        return percentage_basis_points(value)
    except ValueError as error:
        raise SourceImportError("invalid discount_percent") from error


def source_date(value: str, field: str, date_format: str = "%m/%d/%Y", optional: bool = False):
    """Parse source dates in their documented format, optionally allowing blanks."""
    if optional and not value:
        return None
    try:
        return datetime.strptime(value, date_format).date()
    except ValueError as error:
        raise SourceImportError(f"invalid {field}") from error


def specs_value(value: str) -> dict[str, str]:
    """Validate the catalog's bounded public specification mapping."""
    result = _parse_specs(value)
    if not isinstance(result, dict) or set(result) - SPEC_KEYS:
        raise SourceImportError("invalid specs fields")
    if any(not isinstance(item, str) for item in result.values()):
        raise SourceImportError("invalid specs fields")
    return result


def _parse_specs(value: str) -> object:
    """Decode one JSON specification object with a bounded import error."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise SourceImportError("invalid specs JSON") from error


def flag(value: str, field: str) -> bool:
    """Parse a source boolean using only explicit 0/1 or true/false values."""
    normalized = value.casefold()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise SourceImportError(f"invalid {field}")


def required(value: str, field: str) -> str:
    """Require a nonblank source text field."""
    if not value.strip():
        raise SourceImportError(f"missing {field}")
    return value.strip()
