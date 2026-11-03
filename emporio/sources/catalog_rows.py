"""Validate the category, product, and promotion CSV datasets."""

from typing import Any

from emporio.catalog.normalize import normalize_text
from emporio.sources.read import SourceImportError
from emporio.sources.schema import flag, integer, money, percent, required, source_date, specs_value


def catalog_rows(raw: dict[str, list[dict[str, str]]]):
    """Validate catalog relationships and return normalized source rows."""
    categories = _categories(raw["categories"])
    category_names = {row["source_id"]: row["name"] for row in categories}
    products = _products(raw["products"], category_names)
    promotions = _promotions(raw["promotions"], {row["source_id"] for row in products})
    return categories, products, promotions


def _categories(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Validate category identifiers and required customer-facing text."""
    result = []
    for row in rows:
        result.append(
            {
                "source_id": integer(row["category_id"], "category_id", 1),
                "name": required(row["name"], "category name"),
                "description": row["description"].strip(),
            }
        )
    _unique(result, "source_id", "category_id")
    return result


def _products(rows: list[dict[str, str]], categories: dict[int, str]) -> list[dict[str, Any]]:
    """Validate products, including category, price, status, and specs."""
    result = [_product(row, categories) for row in rows]
    _unique(result, "source_id", "product_id")
    return result


def _product(row: dict[str, str], categories: dict[int, str]) -> dict[str, Any]:
    """Validate and normalize one source product record."""
    category_id = integer(row["category_id"], "category_id", 1)
    if category_id not in categories:
        raise SourceImportError("unknown product category")
    status = required(row["status"], "status")
    if status not in {"active", "coming_soon", "discontinued"}:
        raise SourceImportError("invalid status")
    specs = specs_value(row["specs"])
    name = required(row["name"], "product name")
    return _product_record(row, category_id, categories[category_id], status, specs, name)


def _product_record(
    row: dict[str, str],
    category_id: int,
    category_name: str,
    status: str,
    specs: dict[str, str],
    name: str,
) -> dict[str, Any]:
    """Build the normalized persistence fields for one validated product."""
    return {
        "source_id": integer(row["product_id"], "product_id", 1),
        "category_id": category_id,
        "normalized_category": normalize_text(category_name),
        "name": name,
        "normalized_name": normalize_text(name),
        "normalized_search_text": normalize_text(
            " ".join([name, category_name, row["description"], *specs.values()])
        ),
        "description": row["description"].strip(),
        "base_cents": money(row["price_brl"], "price_brl"),
        "stock_quantity": integer(row["stock_quantity"], "stock_quantity"),
        "status": status,
        "specs": specs,
        "created_at": source_date(row["created_at"], "created_at", "%Y-%m-%d"),
    }


def _promotions(rows: list[dict[str, str]], products: set[int]) -> list[dict[str, Any]]:
    """Validate promotion identifiers, percentages, and product references."""
    result = []
    for row in rows:
        product_id = integer(row["product_id"], "product_id", 1)
        if product_id not in products:
            raise SourceImportError("unknown promotion product")
        result.append(
            {
                "source_id": integer(row["promotion_id"], "promotion_id", 1),
                "product_id": product_id,
                "discount_basis_points": percent(row["discount_percent"]),
                "description": required(row["description"], "promotion description"),
                "is_active": flag(row["is_active"], "is_active"),
            }
        )
    _unique(result, "source_id", "promotion_id")
    return result


def _unique(rows: list[dict[str, Any]], field: str, label: str) -> None:
    """Reject repeated source identity values."""
    values = [row[field] for row in rows]
    if len(values) != len(set(values)):
        raise SourceImportError(f"duplicate {label}")
