"""Validate all six CSV datasets before creating an active snapshot."""

from typing import Any

from emporio.sources.catalog_rows import catalog_rows
from emporio.sources.order_rows import order_rows


def validate_sources(raw: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, Any]]]:
    """Return normalized rows after validating every cross-source reference."""
    categories, products, promotions = catalog_rows(raw)
    customers, orders, items = order_rows(raw, {int(row["source_id"]) for row in products})
    return {
        "categories": categories,
        "products": products,
        "promotions": promotions,
        "customers": customers,
        "orders": orders,
        "order_items": items,
    }
