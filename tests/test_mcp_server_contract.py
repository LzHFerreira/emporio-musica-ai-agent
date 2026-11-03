"""In-process contracts for MCP authorization and bounded dispatch."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, Mock, patch

from django.test import SimpleTestCase

from emporio.chat import mcp_server


class MCPApplicationContractTests(SimpleTestCase):
    def test_registered_tools_match_the_four_public_schemas(self):
        tools = asyncio.run(mcp_server.list_tools())
        self.assertEqual({tool.name for tool in tools}, set(mcp_server._TOOLS))
        self.assertTrue(all(tool.inputSchema.get("additionalProperties") is False for tool in tools))

    def test_call_uses_server_sender_and_active_source_version(self):
        queryset = Mock()
        queryset.values_list.return_value.first.return_value = "bundle-v7"
        handler = Mock(return_value={"outcome": "found", "data": [{"name": "Yamaha C40"}]})
        with patch.object(mcp_server.SourceSnapshot.objects, "filter", return_value=queryset), patch.object(mcp_server, "_handlers", return_value={"search_catalog": handler}), patch.object(mcp_server, "close_old_connections"), patch.dict(os.environ, {"EMPORIO_MCP_SENDER": "5567998123456"}):
            result = mcp_server._invoke("search_catalog", {"query": "Yamaha C40"})
        handler.assert_called_once_with({"query": "Yamaha C40"}, "5567998123456", "bundle-v7")
        self.assertEqual(result["data"][0]["name"], "Yamaha C40")

    def test_call_tool_serializes_a_bounded_dispatch_result(self):
        dispatched = {"outcome": "found", "data": [{"name": "Yamaha C40"}]}
        with patch.object(mcp_server.asyncio, "to_thread", new=AsyncMock(return_value=dispatched)) as invoke:
            result = asyncio.run(mcp_server.call_tool("search_catalog", {"query": "Yamaha C40"}))
        invoke.assert_awaited_once_with(mcp_server._invoke, "search_catalog", {"query": "Yamaha C40"})
        self.assertEqual(json.loads(result[0].text), dispatched)

    def test_invalid_and_failed_calls_return_bounded_results(self):
        with patch.object(mcp_server, "close_old_connections"):
            self.assertEqual(mcp_server._invoke("unlisted", {} )["error_category"], "invalid_arguments")
            public = mcp_server._invoke("search_catalog", {"sender": "forged"})
            restricted = mcp_server._invoke("list_own_orders", {"sender": "forged"})
        self.assertEqual(public["error_category"], "invalid_arguments")
        self.assertEqual((restricted["outcome"], restricted["data"]), ("denied", []))

    def test_source_or_handler_failures_never_leak_restricted_data(self):
        with patch.object(mcp_server, "close_old_connections"), patch.object(mcp_server.SourceSnapshot.objects, "filter", side_effect=RuntimeError("db unavailable")):
            public = mcp_server._invoke("search_catalog", {"query": "guitar"})
            restricted = mcp_server._invoke("list_own_orders", {})
        self.assertEqual(public["error_category"], "source_unavailable")
        self.assertEqual((restricted["outcome"], restricted["data"]), ("denied", []))
