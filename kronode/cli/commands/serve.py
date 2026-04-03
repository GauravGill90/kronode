"""kronode serve — start MCP server."""
import asyncio

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--http", is_flag=True, help="Use HTTP/SSE transport (for Cursor, remote)")
@click.option("--port", default=8001, help="HTTP port (default: 8001)")
def serve(http: bool, port: int):
    """Start the Kronode MCP server.

    Default: stdio transport (for Claude Code, Codex).
    Use --http for Cursor, Copilot, and remote access.
    """
    from kronode.core.config import get_settings
    from kronode.mcp.server import mcp, configure

    settings = get_settings()
    configure(org_id=settings.org_id)

    if http:
        console.print(f"[bold]Kronode MCP[/bold] — HTTP on port {port}")
        asyncio.run(mcp.run_async(transport="sse", host="0.0.0.0", port=port))
    else:
        # stdio — no console output (it would break the MCP protocol)
        import sys, logging
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        asyncio.run(mcp.run_stdio_async())
