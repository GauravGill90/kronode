"""Kronode MCP Server entry point.

Usage:
    python -m app.mcp.main                          # uses KRONODE_TOKEN env var
    python -m app.mcp.main --token kron_xxxxx        # explicit token
    python -m app.mcp.main --org-id 57               # dev mode, skip auth
    python -m app.mcp.main --transport http           # HTTP/SSE transport (for Cursor, Copilot, etc.)

The server runs on stdio transport by default (for `claude mcp add`).
Use --transport http for remote/team deployment.
"""
import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


async def _resolve_org(token: str | None, org_id: int | None) -> tuple[int, str, str]:
    """Resolve org_id, repo_url, github_token from API token or direct org_id."""
    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig

    if org_id:
        # Dev mode — direct org_id
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            cfg = (await db.execute(
                select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
            )).scalar_one_or_none()
            if not cfg:
                raise ValueError(f"No onboarding config for org {org_id}")
            return org_id, cfg.repo_url or "", cfg.github_access_token or ""

    if token:
        # Production mode — resolve from API key
        from app.mcp.auth import validate_token
        org = await validate_token(token)
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            cfg = (await db.execute(
                select(OnboardingConfig).where(OnboardingConfig.org_id == org.org_id)
            )).scalar_one_or_none()
            return org.org_id, (cfg.repo_url if cfg else ""), (cfg.github_access_token if cfg else "")

    raise ValueError("Provide --token or --org-id (or set KRONODE_TOKEN env var)")


async def run():
    import os

    parser = argparse.ArgumentParser(description="Kronode MCP Server")
    parser.add_argument("--token", default=os.environ.get("KRONODE_TOKEN"), help="Kronode API token (kron_...)")
    parser.add_argument("--org-id", type=int, default=None, help="Direct org ID (dev mode, skips auth)")
    parser.add_argument(
        "--transport", default=os.environ.get("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "http"],
        help="Transport: stdio (default, for Claude Code) or http (for Cursor, Copilot, remote)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="HTTP port (default: 8001)")
    args = parser.parse_args()

    try:
        org_id, repo_url, github_token = await _resolve_org(args.token, args.org_id)
    except Exception as e:
        logger.error(f"Failed to resolve org: {e}")
        sys.exit(1)

    from app.mcp.server import mcp, configure
    configure(org_id=org_id, repo_url=repo_url, github_token=github_token)

    if args.transport == "http":
        logger.info(f"[KronodeMCP] Starting HTTP server for org {org_id} on {args.host}:{args.port}")
        await mcp.run_async(transport="sse", host=args.host, port=args.port)
    else:
        logger.info(f"[KronodeMCP] Starting stdio server for org {org_id}")
        await mcp.run_stdio_async()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
