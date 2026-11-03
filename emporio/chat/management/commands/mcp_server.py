"""Run the local stdio MCP server for customer-facing read-only tools."""

import asyncio

from django.core.management.base import BaseCommand

from emporio.chat.mcp_server import server
from emporio.chat.mcp_stdio import run_stdio


class Command(BaseCommand):
    """Serve the customer tools over MCP stdio."""

    help = "Run the local Empório MCP server"
    requires_system_checks = []

    def handle(self, *args, **options):
        """Start the protocol server without printing non-protocol output."""
        asyncio.run(run_stdio(server))
