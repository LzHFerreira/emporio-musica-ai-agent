"""Public customer agent façade and call-time trusted tool registry."""

from collections.abc import Callable
from typing import Any, NotRequired, TypedDict

from emporio.agent_tools import ToolHandler
from emporio.agent_turn import run_turn as _run_turn
from emporio.catalog import search_catalog
from emporio.orders_access import get_own_order_status as _get_order
from emporio.orders_access import list_own_orders as _list_orders
from emporio.policy import lookup_public_policy, read_store_manual


class _TurnOptions(TypedDict):
    snapshot_version: str | None
    handlers: dict[str, ToolHandler]
    history: NotRequired[list[dict[str, str]]]


def list_own_orders(sender: str, *, page: int, snapshot_version: str | None) -> dict[str, Any]:
    """Resolve an owned-order page through the trusted sender boundary."""
    return _list_orders(sender, page=page, snapshot_version=snapshot_version)


def get_own_order_status(
    sender: str, *, order_id: int, snapshot_version: str | None
) -> dict[str, Any]:
    """Resolve one order status only within the trusted sender scope."""
    return _get_order(sender, order_id=order_id, snapshot_version=snapshot_version)


def run_turn(
    text: str,
    *,
    sender: str,
    model_client: Callable[..., dict[str, Any]],
    snapshot_version: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run one bounded turn with handlers resolved from this façade at call time."""
    options: _TurnOptions = {
        "snapshot_version": snapshot_version,
        "handlers": _handlers(),
    }
    if history:
        options["history"] = history
    return _run_turn(
        text,
        sender=sender,
        model_client=model_client,
        **options,
    )


def _handlers() -> dict[str, ToolHandler]:
    return {
        "search_catalog": _catalog_tool,
        "lookup_public_policy": _policy_tool,
        "read_store_manual": lambda _a, _s, v: read_store_manual(snapshot_version=v or None),
        "list_own_orders": _list_tool,
        "get_own_order_status": _status_tool,
    }


def _catalog_tool(args: dict[str, Any], sender: str, version: str) -> dict[str, Any]:
    del sender
    return search_catalog(**args, snapshot_version=version or None)


def _policy_tool(args: dict[str, Any], sender: str, version: str) -> dict[str, Any]:
    del sender
    return lookup_public_policy(**args, snapshot_version=version or None)


def _list_tool(args: dict[str, Any], sender: str, version: str) -> dict[str, Any]:
    return list_own_orders(sender, page=args.get("page", 1), snapshot_version=version or None)


def _status_tool(args: dict[str, Any], sender: str, version: str) -> dict[str, Any]:
    return get_own_order_status(sender, order_id=args["order_id"], snapshot_version=version or None)
