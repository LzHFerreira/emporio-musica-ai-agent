"""Sender-scoped read-only order projections."""

import re
from typing import Any

from django.db.utils import DatabaseError

from emporio.catalog.models import SourceSnapshot
from emporio.orders.models import Customer, Order


def list_own_orders(sender: str, *, page: int, snapshot_version: str | None) -> dict[str, Any]:
    """Return five newest owned orders after a unique sender match."""
    if not _valid_page(page):
        return _result("denied", error="restricted_unavailable")
    try:
        return _list_page(sender, page, snapshot_version)
    except (DatabaseError, AttributeError, TypeError):
        return _result("denied", error="restricted_unavailable")


def get_own_order_status(
    sender: str, *, order_id: int, snapshot_version: str | None
) -> dict[str, Any]:
    """Return requested tracking fields only for an order in sender scope."""
    if type(order_id) is not int or order_id < 1:
        return _result("denied", error="restricted_unavailable")
    try:
        return _one_order(sender, order_id, snapshot_version)
    except (DatabaseError, AttributeError, TypeError):
        return _result("denied", error="restricted_unavailable")


def sender_binding(sender: str, snapshot_version: str | None) -> str:
    """Return the internal unique match key for dispatch-time authorization checks."""
    try:
        _, customer = _scope(sender, snapshot_version)
    except (DatabaseError, AttributeError, TypeError):
        return ""
    return str(customer.pk) if customer is not None else ""


def _valid_page(page: int) -> bool:
    return type(page) is int and 1 <= page <= 20


def _list_page(sender, page, version):
    snapshot, customer = _scope(sender, version)
    if customer is None:
        return _result("denied", error="restricted_unavailable")
    assert snapshot is not None
    offset = (page - 1) * 5
    rows = list(_orders(snapshot, customer)[offset : offset + 6])
    data = [
        {"order_id": row.source_id, "order_date": row.order_date.isoformat(), "status": row.status}
        for row in rows[:5]
    ]
    return _result(
        "found" if data else "not_found",
        data=data,
        page=page,
        more=len(rows) > 5,
        version=snapshot.version,
    )


def _orders(snapshot, customer):
    return Order.objects.filter(snapshot=snapshot, customer=customer).order_by(
        "-order_date", "-source_id"
    )


def _one_order(sender, order_id, version):
    snapshot, customer = _scope(sender, version)
    if customer is None:
        return _result("denied", error="restricted_unavailable")
    order = Order.objects.filter(snapshot=snapshot, customer=customer, source_id=order_id).first()
    return _project_order(order, snapshot)


def _project_order(order, snapshot):
    if order is None:
        return _result("denied", error="restricted_unavailable")
    data = [
        {
            "order_id": order.source_id,
            "status": order.status,
            "tracking_code": order.tracking_code or None,
            "estimated_delivery": order.estimated_delivery.isoformat()
            if order.estimated_delivery
            else None,
        }
    ]
    return _result("found", data=data, version=snapshot.version)


def _scope(sender: str, version: str | None):
    if not _valid_sender(sender):
        return None, None
    snapshot = _snapshot(version)
    return _matched_customer(snapshot, sender)


def _matched_customer(snapshot, sender):
    if snapshot is None:
        return None, None
    matches = [
        row
        for row in Customer.objects.filter(snapshot=snapshot)
        if _stored_phone(row.phone) == _canonical(sender)
    ]
    return (snapshot, matches[0]) if len(matches) == 1 else (snapshot, None)


def _snapshot(version):
    snapshots = SourceSnapshot.objects.all()
    return (
        snapshots.filter(version=version).first()
        if version
        else snapshots.filter(is_active=True).first()
    )


def _valid_sender(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{7,14}", value) is not None


def _canonical(value: str) -> str:
    return f"+{value}"


def _stored_phone(value: str) -> str | None:
    if not isinstance(value, str) or re.search(r"[^0-9+ ().-]", value):
        return None
    compact = re.sub(r"[ ().-]", "", value)
    digits = compact.removeprefix("+")
    return _canonical_br_phone(digits, compact)


def _canonical_br_phone(digits: str, compact: str) -> str | None:
    if digits.startswith("0055"):
        digits = digits[2:]
    if _domestic_phone(digits, compact):
        digits = "55" + digits
    return f"+{digits}" if _brazilian_phone(digits) else None


def _domestic_phone(digits: str, compact: str) -> bool:
    return len(digits) in {10, 11} and not compact.startswith(("+", "00"))


def _brazilian_phone(digits: str) -> bool:
    return digits.startswith("55") and len(digits) in {12, 13}


def _result(outcome: str, *, data=None, page=None, more=False, version=None, error=None):
    return {
        "outcome": outcome,
        "data": data or [],
        "sources": [
            {
                "type": "orders",
                "label": "Seus pedidos",
                "page": page,
                "section": None,
                "bundle_version": version,
            }
        ]
        if data
        else [],
        "page": page,
        "pagination_restarted": False,
        "has_more": more,
        "error_category": error,
    }
