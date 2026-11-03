"""Validate customer, order, and order-item CSV datasets."""

from typing import Any

from emporio.sources.read import SourceImportError
from emporio.sources.schema import integer, money, required, source_date


def order_rows(raw: dict[str, list[dict[str, str]]], product_ids: set[int]):
    """Validate order relationships and return normalized source rows."""
    customers = _customers(raw["customers"])
    orders = _orders(raw["orders"], {row["source_id"] for row in customers})
    items = _items(raw["order_items"], {row["source_id"] for row in orders}, product_ids)
    return customers, orders, items


def _customers(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Validate customer identity and source contact fields."""
    result = []
    for row in rows:
        result.append(
            {
                "source_id": integer(row["customer_id"], "customer_id", 1),
                "name": required(row["name"], "customer name"),
                "phone": row["phone"].strip(),
                "email": row["email"].strip(),
                "city": row["city"].strip(),
            }
        )
    _unique(result, ("source_id",), "customer_id")
    return result


def _orders(rows: list[dict[str, str]], customers: set[int]) -> list[dict[str, Any]]:
    """Validate order identity, ownership reference, date, and total."""
    result = []
    for row in rows:
        customer_id = integer(row["customer_id"], "customer_id", 1)
        if customer_id not in customers:
            raise SourceImportError("unknown order customer")
        result.append(
            {
                "source_id": integer(row["order_id"], "order_id", 1),
                "customer_id": customer_id,
                "order_date": source_date(row["order_date"], "order_date"),
                "status": required(row["status"], "order status"),
                "total_cents": money(row["total_brl"], "total_brl"),
                "payment_method": required(row["payment_method"], "payment_method"),
                "tracking_code": row["tracking_code"].strip(),
                "estimated_delivery": source_date(
                    row["estimated_delivery"], "estimated_delivery", optional=True
                ),
                "notes": row["notes"].strip(),
            }
        )
    _unique(result, ("source_id",), "order_id")
    return result


def _items(
    rows: list[dict[str, str]], orders: set[int], products: set[int]
) -> list[dict[str, Any]]:
    """Validate positive quantities and order/product relationships."""
    result = []
    for row in rows:
        order_id = integer(row["order_id"], "order_id", 1)
        product_id = integer(row["product_id"], "product_id", 1)
        if order_id not in orders or product_id not in products:
            raise SourceImportError("unknown order-item reference")
        result.append(
            {
                "order_id": order_id,
                "product_id": product_id,
                "quantity": integer(row["quantity"], "quantity", 1),
            }
        )
    _unique(result, ("order_id", "product_id"), "order-item pair")
    return result


def _unique(rows: list[dict[str, Any]], fields: tuple[str, ...], label: str) -> None:
    """Reject repeated scalar or composite identities."""
    identities = [tuple(row[field] for field in fields) for row in rows]
    if len(identities) != len(set(identities)):
        raise SourceImportError(f"duplicate {label}")
