"""Run the MCP SDK's standard input/output transport."""

from mcp.server import Server
from mcp.server.stdio import stdio_server


async def run_stdio(server: Server) -> None:
    """Run the SDK transport without altering protocol framing or stream lifecycle."""
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())
