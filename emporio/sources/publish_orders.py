"""Persist customer, order, and order-item snapshot records."""

from typing import Any

from emporio.catalog.models import Product, SourceSnapshot
from emporio.orders.models import Customer, Order, OrderItem


def insert_orders(snapshot: SourceSnapshot, rows: dict[str, list[dict[str, Any]]]) -> None:
    """Persist private historical rows after the catalog records exist."""
    customers = _insert_customers(snapshot, rows["customers"])
    orders = _insert_order_records(snapshot, rows["orders"], customers)
    products = {row.source_id: row for row in Product.objects.filter(snapshot=snapshot)}
    _insert_order_items(snapshot, rows["order_items"], orders, products)


def _insert_customers(snapshot: SourceSnapshot, rows: list[dict[str, Any]]) -> dict[int, Customer]:
    """Persist customers and return source-ID foreign-key lookups."""
    Customer.objects.bulk_create([Customer(snapshot=snapshot, **row) for row in rows])
    return {row.source_id: row for row in Customer.objects.filter(snapshot=snapshot)}


def _insert_order_records(
    snapshot: SourceSnapshot,
    rows: list[dict[str, Any]],
    customers: dict[int, Customer],
) -> dict[int, Order]:
    """Persist orders linked to source customers and return their lookup map."""
    orders = []
    for source in rows:
        data = dict(source)
        customer_id = int(data.pop("customer_id"))
        data["customer"] = customers[customer_id]
        orders.append(Order(snapshot=snapshot, **data))
    Order.objects.bulk_create(orders)
    return {row.source_id: row for row in Order.objects.filter(snapshot=snapshot)}


def _insert_order_items(
    snapshot: SourceSnapshot,
    rows: list[dict[str, Any]],
    orders: dict[int, Order],
    products: dict[int, Product],
) -> None:
    """Persist validated quantity links after orders and products exist."""
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                snapshot=snapshot,
                order=orders[int(row["order_id"])],
                product=products[int(row["product_id"])],
                quantity=row["quantity"],
            )
            for row in rows
        ]
    )
