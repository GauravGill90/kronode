"""Kronode MCP Server entry point.

Usage (open-source):
    kronode serve              # stdio (Claude Code, Codex)
    kronode serve --http       # HTTP/SSE (Cursor, Copilot, remote)

Usage (direct):
    python -m kronode.mcp.main              # reads from ~/.kronode/config.toml
    python -m kronode.mcp.main --http       # HTTP mode
"""
import asyncio
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


async def run():
    parser = argparse.ArgumentParser(description="Kronode MCP Server")
    parser.add_argument("--http", action="store_true", help="Use HTTP/SSE transport")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--port", type=int, default=8001, help="HTTP port")
    args = parser.parse_args()

    # Initialize database
    from kronode.core.database import init_db
    await init_db()

    # Configure MCP server
    from kronode.core.config import get_settings
    from kronode.mcp.server import mcp, configure

    settings = get_settings()
    configure(org_id=settings.org_id)

    if args.http:
        logger.info(f"[KronodeMCP] Starting HTTP server on {args.host}:{args.port}")
        await mcp.run_async(transport="sse", host=args.host, port=args.port)
    else:
        logger.info("[KronodeMCP] Starting stdio server")
        await mcp.run_stdio_async()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
