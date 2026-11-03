"""Strict runtime validation for public catalog tool arguments."""

import re
from decimal import Decimal
from typing import Any

ARGUMENTS = {
    "query",
    "mode",
    "category",
    "max_price_brl",
    "payment_method",
    "available_only",
    "page",
}
PAYMENTS = {"unspecified", "pix", "debit", "credit", "boleto", "mixed"}
PRICE_PATTERN = re.compile(r"^(0|[1-9][0-9]{0,6})(\.[0-9]{1,2})?$")


def parse_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Return normalized defaults, or None if arguments violate the schema."""
    if set(arguments) - ARGUMENTS:
        return None
    values = {
        "query": "",
        "mode": "search",
        "category": None,
        "max_price_brl": None,
        "payment_method": "unspecified",
        "available_only": False,
        "page": 1,
    } | arguments
    if not _schema_valid(values):
        return None
    result = dict(values)
    query = values["query"]
    if not isinstance(query, str):
        return None
    result["query"] = query.strip()
    price = values["max_price_brl"]
    result["price_cents"] = int(Decimal(price) * 100) if price is not None else None
    return result


def _schema_valid(values: dict[str, Any]) -> bool:
    """Check each independently typed section of the tool schema."""
    return all(
        (
            _valid_query(values),
            _valid_category(values["category"]),
            _valid_price(values["max_price_brl"]),
            _valid_payment(values["payment_method"], values["available_only"]),
            _valid_page(values["page"]),
        )
    )


def _valid_query(values: dict[str, Any]) -> bool:
    """Validate query text and search mode."""
    query = values["query"]
    mode = values["mode"]
    return (
        isinstance(query, str)
        and len(query) <= 160
        and isinstance(mode, str)
        and mode in {"search", "resolve"}
    )


def _valid_category(category: Any) -> bool:
    """Validate the optional descriptive category filter."""
    return category is None or isinstance(category, str) and 1 <= len(category) <= 80


def _valid_price(price: Any) -> bool:
    """Validate the optional decimal string budget."""
    return price is None or isinstance(price, str) and PRICE_PATTERN.fullmatch(price) is not None


def _valid_payment(payment: Any, available_only: Any) -> bool:
    """Validate the payment enumeration and exact boolean filter."""
    return isinstance(payment, str) and payment in PAYMENTS and type(available_only) is bool


def _valid_page(page: Any) -> bool:
    """Validate a bounded integer page without accepting booleans."""
    return type(page) is int and 1 <= page <= 20
