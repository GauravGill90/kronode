"""Kronode Slack Bot — ask @kronode questions directly in Slack.

Examples:
  @kronode what are the conventions for auth-service?
  @kronode critique this ticket: DEECO-1234
  @kronode what files usually change with useCertExchange.ts?
  /kronode conventions auth

Uses slack-bolt (Python) for event handling.
"""
import logging
import re

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Slack app — tokens come from env or onboarding config
bolt_app = AsyncApp(
    token=settings.slack_client_secret,  # fallback; real token resolved per-workspace
    signing_secret=settings.slack_signing_secret,
    token_verification_enabled=bool(settings.slack_signing_secret),
)

handler = AsyncSlackRequestHandler(bolt_app)


async def _resolve_org_from_team(team_id: str) -> tuple[int, str] | None:
    """Look up org_id and bot_token from Slack team_id."""
    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Find org with matching Slack channel
        configs = (await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.slack_bot_token.isnot(None))
        )).scalars().all()

        for cfg in configs:
            if cfg.slack_bot_token:
                return cfg.org_id, cfg.slack_bot_token

    return None


async def _get_context_response(org_id: int, query: str) -> str:
    """Route a natural language query to the appropriate context provider."""
    from app.mcp.server import configure, get_context, get_doc, get_file_companions

    configure(org_id=org_id)

    # Simple intent classification
    query_lower = query.lower().strip()

    # File companions
    file_match = re.search(r'(?:files?\s+(?:that\s+)?change\s+with|companions?\s+(?:for|of))\s+(\S+)', query_lower)
    if file_match:
        file_path = file_match.group(1)
        result = await get_file_companions(file_path)
        companions = result.get("companions", [])
        if not companions:
            return f"No companion files found for `{file_path}`."
        lines = [f"*Files that usually change with `{file_path}`:*\n"]
        for c in companions[:10]:
            lines.append(f"• `{c['path']}` ({c['co_change_pct']}% co-change rate)")
        return "\n".join(lines)

    # Doc search
    if any(kw in query_lower for kw in ["doc", "documentation", "policy", "spec", "specification"]):
        result = await get_doc(query)
        if result.get("content"):
            title = result.get("title", "Document")
            content = result["content"][:2000]
            return f"*{title}*\n\n{content}"
        return f"No documentation found matching: {query}"

    # Default: get_context
    result = await get_context(query, files_touched=None)
    conventions = result.get("conventions", [])
    doc_chunks = result.get("doc_chunks", [])

    lines = []
    if conventions:
        lines.append("*Relevant conventions:*\n")
        for c in conventions[:8]:
            rule = c.get("rule", c) if isinstance(c, dict) else str(c)
            lines.append(f"• {rule[:200]}")

    if doc_chunks:
        lines.append("\n*Relevant documentation:*\n")
        for d in doc_chunks[:3]:
            heading = d.get("heading", "")
            content = d.get("content", "")[:300]
            lines.append(f"• *{heading}*: {content}")

    if not lines:
        return f"No context found for: {query}"

    return "\n".join(lines)


@bolt_app.event("app_mention")
async def handle_mention(event, say, client):
    """Handle @kronode mentions."""
    text = event.get("text", "")
    team_id = event.get("team", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Strip the bot mention
    query = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not query:
        await say("What would you like to know? Try asking about conventions, documentation, or file companions.", thread_ts=thread_ts)
        return

    org_info = await _resolve_org_from_team(team_id)
    if not org_info:
        await say("Kronode isn't configured for this workspace yet. Complete onboarding at your Kronode dashboard.", thread_ts=thread_ts)
        return

    org_id, bot_token = org_info

    try:
        response = await _get_context_response(org_id, query)
        await say(response, thread_ts=thread_ts)
    except Exception as e:
        logger.error(f"[SlackBot] Error handling mention: {e}")
        await say(f"Sorry, something went wrong: {str(e)[:200]}", thread_ts=thread_ts)


@bolt_app.command("/kronode")
async def handle_slash_command(ack, respond, command):
    """Handle /kronode slash commands."""
    await ack()

    text = command.get("text", "").strip()
    team_id = command.get("team_id", "")

    if not text:
        await respond("Usage: `/kronode <question>` — e.g., `/kronode conventions for auth service`")
        return

    org_info = await _resolve_org_from_team(team_id)
    if not org_info:
        await respond("Kronode isn't configured for this workspace. Complete onboarding first.")
        return

    org_id, bot_token = org_info

    try:
        response = await _get_context_response(org_id, text)
        await respond(response)
    except Exception as e:
        logger.error(f"[SlackBot] Error handling command: {e}")
        await respond(f"Error: {str(e)[:200]}")
