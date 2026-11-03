"""Register the four bounded customer services with the MCP SDK."""

import asyncio
import json
import os
from typing import Any

from django.db import close_old_connections
from mcp.server import Server
from mcp.types import TextContent, Tool

from emporio.agent import _handlers
from emporio.agent_schemas import TOOL_SCHEMAS, arguments_valid
from emporio.catalog.models import SourceSnapshot

server = Server("emporio-musica")
_TOOLS = {item["function"]["name"]: item["function"] for item in TOOL_SCHEMAS}
_RESTRICTED = {"list_own_orders", "get_own_order_status"}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the exact existing customer-tool schemas."""
    return [
        Tool(name=name, description=schema["description"], inputSchema=schema["parameters"])
        for name, schema in _TOOLS.items()
    ]


@server.call_tool(validate_input=False)
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Validate and invoke one tool using server-owned identity and source scope."""
    result = await asyncio.to_thread(_invoke, name, arguments)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _invoke(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    close_old_connections()
    try:
        return _dispatch_tool(name, arguments)
    except Exception:
        return _denied() if name in _RESTRICTED else _error("source_unavailable")
    finally:
        close_old_connections()


def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    error = _argument_error(name, arguments)
    if error:
        return error
    version = (
        SourceSnapshot.objects.filter(is_active=True).values_list("version", flat=True).first()
    )
    sender = os.environ.get("EMPORIO_MCP_SENDER", "")
    return _handlers()[name](arguments, sender, version or "")


def _argument_error(name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    if name not in _TOOLS:
        return _error("invalid_arguments")
    if isinstance(arguments, dict) and arguments_valid(name, arguments):
        return None
    return _denied() if name in _RESTRICTED else _error("invalid_arguments")


def _denied() -> dict[str, Any]:
    return {
        "outcome": "denied",
        "data": [],
        "sources": [],
        "page": None,
        "pagination_restarted": False,
        "has_more": False,
        "error_category": "restricted_unavailable",
    }


def _error(category: str) -> dict[str, Any]:
    return {
        "outcome": "error",
        "data": [],
        "sources": [],
        "page": None,
        "pagination_restarted": False,
        "has_more": False,
        "error_category": category,
    }
