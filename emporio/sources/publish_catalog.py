"""Persist catalog rows and snapshot-specific payable-price projections."""

from collections import Counter
from typing import Any

from emporio.catalog.models import Category, Product, Promotion, SourceSnapshot
from emporio.catalog.pricing import discounted_cents


def insert_catalog(snapshot: SourceSnapshot, rows: dict[str, list[dict[str, Any]]]) -> None:
    """Persist category, product, and promotion rows in foreign-key order."""
    Category.objects.bulk_create([Category(snapshot=snapshot, **row) for row in rows["categories"]])
    products = _product_models(snapshot, rows["products"], rows["promotions"])
    Product.objects.bulk_create(products)
    product_map = {row.source_id: row for row in Product.objects.filter(snapshot=snapshot)}
    _insert_promotions(snapshot, rows["promotions"], product_map)


def _product_models(
    snapshot: SourceSnapshot,
    rows: list[dict[str, Any]],
    promotions: list[dict[str, Any]],
) -> list[Product]:
    """Resolve category and promotion maps before constructing product rows."""
    categories = {row.source_id: row for row in Category.objects.filter(snapshot=snapshot)}
    counts, active = _active_promotions(promotions)
    return [_product_model(snapshot, row, categories, counts, active) for row in rows]


def _active_promotions(
    rows: list[dict[str, Any]],
) -> tuple[Counter[int], dict[int, dict[str, Any]]]:
    """Index active promotion counts and unique candidate records by product."""
    active = [row for row in rows if row["is_active"]]
    counts = Counter(int(row["product_id"]) for row in active)
    return counts, {int(row["product_id"]): row for row in active}


def _product_model(
    snapshot: SourceSnapshot,
    source: dict[str, Any],
    categories: dict[int, Category],
    counts: Counter[int],
    promotions: dict[int, dict[str, Any]],
) -> Product:
    """Build one product with an immutable price projection for this snapshot."""
    data = dict(source)
    category_id = int(data.pop("category_id"))
    product_id = int(data["source_id"])
    data["category"] = categories[category_id]
    data.update(
        _prices(
            int(data["base_cents"]),
            counts[product_id],
            promotions.get(product_id),
            snapshot.pix_basis_points,
        )
    )
    return Product(snapshot=snapshot, **data)


def _insert_promotions(
    snapshot: SourceSnapshot, rows: list[dict[str, Any]], products: dict[int, Product]
) -> None:
    """Persist promotion rows after their product foreign keys exist."""
    Promotion.objects.bulk_create(
        [
            Promotion(
                snapshot=snapshot,
                product=products[int(row["product_id"])],
                **{key: value for key, value in row.items() if key != "product_id"},
            )
            for row in rows
        ]
    )


def _prices(base: int, count: int, promotion: dict[str, Any] | None, pix: int) -> dict[str, Any]:
    """Materialize one unstacked promotion or the reviewed PIX price."""
    if count > 1:
        return {
            "standard_payable_cents": base,
            "pix_payable_cents": base,
            "pricing_state": "ambiguous",
        }
    if promotion is not None:
        amount = discounted_cents(base, int(promotion["discount_basis_points"]))
        return {
            "standard_payable_cents": amount,
            "pix_payable_cents": amount,
            "pricing_state": "promotion",
        }
    return {
        "standard_payable_cents": base,
        "pix_payable_cents": discounted_cents(base, pix),
        "pricing_state": "pix",
    }
