"""Project one active SQLite source table into its canonical CSV columns."""

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from emporio.catalog.models import Category, Product, Promotion, SourceSnapshot
from emporio.orders.models import Customer, Order, OrderItem

SourceRows = list[dict[str, str]]
RowReader = Callable[[SourceSnapshot], SourceRows]


def source_rows(snapshot: SourceSnapshot, source: str) -> SourceRows:
    """Read the selected snapshot table only, retaining canonical field names."""
    readers: dict[str, RowReader] = {
        "categories": _category_rows,
        "products": _product_rows,
        "promotions": _promotion_rows,
        "customers": _customer_rows,
        "orders": _order_rows,
        "order_items": _item_rows,
    }
    try:
        return readers[source](snapshot)
    except KeyError as error:
        raise ValueError("unknown source") from error


def _category_rows(snapshot: SourceSnapshot) -> SourceRows:
    return [
        {"category_id": str(row.source_id), "name": row.name, "description": row.description}
        for row in Category.objects.filter(snapshot=snapshot).order_by("source_id")
    ]


def _product_rows(snapshot: SourceSnapshot) -> SourceRows:
    products = Product.objects.filter(snapshot=snapshot).select_related("category")
    return [
        {
            "product_id": str(row.source_id),
            "price_brl": _decimal(row.base_cents),
            "name": row.name,
            "category_id": str(row.category.source_id),
            "description": row.description,
            "stock_quantity": str(row.stock_quantity),
            "status": row.status,
            "specs": json.dumps(row.specs, ensure_ascii=False, separators=(",", ":")),
            "created_at": row.created_at.isoformat(),
        }
        for row in products.order_by("source_id")
    ]


def _promotion_rows(snapshot: SourceSnapshot) -> SourceRows:
    promotions = Promotion.objects.filter(snapshot=snapshot).select_related("product")
    return [
        {
            "promotion_id": str(row.source_id),
            "product_id": str(row.product.source_id),
            "discount_percent": _decimal(row.discount_basis_points),
            "description": row.description,
            "is_active": "1" if row.is_active else "0",
        }
        for row in promotions.order_by("source_id")
    ]


def _customer_rows(snapshot: SourceSnapshot) -> SourceRows:
    return [
        {
            "customer_id": str(row.source_id),
            "name": row.name,
            "phone": row.phone,
            "email": row.email,
            "city": row.city,
        }
        for row in Customer.objects.filter(snapshot=snapshot).order_by("source_id")
    ]


def _order_rows(snapshot: SourceSnapshot) -> SourceRows:
    orders = Order.objects.filter(snapshot=snapshot).select_related("customer")
    return [
        {
            "order_id": str(row.source_id),
            "customer_id": str(row.customer.source_id),
            "order_date": _date(row.order_date),
            "status": row.status,
            "total_brl": _decimal(row.total_cents),
            "payment_method": row.payment_method,
            "tracking_code": row.tracking_code,
            "estimated_delivery": _date(row.estimated_delivery) if row.estimated_delivery else "",
            "notes": row.notes,
        }
        for row in orders.order_by("source_id")
    ]


def _item_rows(snapshot: SourceSnapshot) -> SourceRows:
    items = OrderItem.objects.filter(snapshot=snapshot).select_related("order", "product")
    return [
        {
            "order_id": str(row.order.source_id),
            "quantity": str(row.quantity),
            "product_id": str(row.product.source_id),
        }
        for row in items.order_by("order__source_id", "product__source_id")
    ]


def _decimal(cents: int) -> str:
    value = format(Decimal(cents) / 100, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def _date(value: date) -> str:
    return f"{value.month}/{value.day}/{value.year}"
