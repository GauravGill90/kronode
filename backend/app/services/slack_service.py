import logging

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


async def post_notification(
    channel_id: str,
    message: str,
    bot_token: str,
    blocks: list | None = None,
) -> str | None:
    """Post a message to a Slack channel. Returns the message ts on success, None on failure."""
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload: dict = {"channel": channel_id, "text": message}
    if blocks:
        payload["blocks"] = blocks

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)

    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] Post to {channel_id} failed: {data.get('error')}")
        return None

    logger.info(f"[Slack] Posted to {channel_id}: {message[:80]}")
    return data.get("ts")


async def post_clarification(
    channel_id: str,
    questions: list[str],
    task_id: str,
    agent_name: str,
    bot_token: str,
) -> tuple[str, str] | None:
    """Post clarification questions to Slack. Returns (ts, real_channel_id) or None on failure.

    chat.postMessage accepts channel names (#kronode) but conversations.replies needs the
    real channel ID (C0XXXXXXX). We capture it from the postMessage response.
    """
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":thinking_face: *{agent_name}* needs a few clarifications before starting:",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": numbered},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Reply in this thread with your answers. Task: `{task_id}`",
                }
            ],
        },
    ]
    fallback = f"{agent_name} needs clarification: {numbered}"
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload: dict = {"channel": channel_id, "text": fallback, "blocks": blocks}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)

    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] post_clarification to {channel_id} failed: {data.get('error')}")
        return None

    ts = data.get("ts")
    real_channel_id = data.get("channel")  # always a channel ID (C0XXXXXXX), never a name
    logger.info(f"[Slack] Posted clarification to {real_channel_id} ts={ts}")
    return ts, real_channel_id


async def get_thread_replies(
    channel_id: str,
    thread_ts: str,
    bot_token: str,
) -> list[str]:
    """Return user reply texts in a thread (excludes the original bot message)."""
    headers = {"Authorization": f"Bearer {bot_token}"}
    params = {"channel": channel_id, "ts": thread_ts}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SLACK_API}/conversations.replies", headers=headers, params=params
        )

    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] conversations.replies failed: {data.get('error')}")
        return []

    messages = data.get("messages", [])
    # messages[0] is the original bot post; skip it, collect user replies
    return [m["text"] for m in messages[1:] if m.get("user")]


async def post_plan_for_approval(
    channel_id: str,
    plan: dict,
    task_id: str,
    agent_name: str,
    confidence_level: str,
    confidence_score: float,
    bot_token: str,
) -> tuple[str, str] | None:
    """Post an implementation plan to Slack for human approval. Returns (ts, channel_id) or None."""
    subtasks = plan.get("subtasks", [])
    dod = plan.get("definition_of_done", [])
    risk_flags = plan.get("risk_flags", [])
    assumptions = plan.get("assumptions", [])
    estimated_files = plan.get("estimated_files", "?")

    # Confidence emoji
    conf_emoji = {"high": ":large_green_circle:", "medium": ":large_yellow_circle:", "low": ":red_circle:"}.get(
        confidence_level, ":white_circle:"
    )

    subtask_text = "\n".join(f"{s['order']}. {s['description']}" for s in subtasks) or "No subtasks"
    dod_text = "\n".join(f"• {d}" for d in dod) or "None"
    risk_text = "\n".join(f"⚠️ {r}" for r in risk_flags) if risk_flags else "None"
    assumption_text = "\n".join(f"• {a}" for a in assumptions) if assumptions else "None"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 {agent_name} — Plan for review"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{conf_emoji} *Confidence: {confidence_level.upper()}* ({confidence_score:.1f})\n"
                    f"Estimated files: {estimated_files}"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Subtasks*\n{subtask_text}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Definition of Done*\n{dod_text}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Risks*\n{risk_text}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Assumptions*\n{assumption_text}"},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Proceeding with implementation. Task: `{task_id}`",
                }
            ],
        },
    ]

    # Add low-confidence warning
    if confidence_level == "low":
        blocks.insert(2, {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":warning: *Low confidence — recommend a human take this ticket.*\n"
                    f"{agent_name} can assist: share context, review the PR, or write tests."
                ),
            },
        })

    fallback = f"{agent_name} plan for review (confidence: {confidence_level}). Reply 'approve' or 'reject'. Task: {task_id}"
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload: dict = {"channel": channel_id, "text": fallback, "blocks": blocks}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)

    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] post_plan_for_approval to {channel_id} failed: {data.get('error')}")
        return None

    ts = data.get("ts")
    real_channel_id = data.get("channel")
    logger.info(f"[Slack] Posted plan for approval to {real_channel_id} ts={ts}")
    return ts, real_channel_id


async def post_conventions_review(
    channel_id: str,
    conventions: list[dict],
    agent_name: str,
    bot_token: str,
    total_count: int = 0,
) -> str | None:
    """Post extracted conventions to Slack for team review.

    Shows the top conventions and asks the team to flag any that are wrong.
    Returns the message ts on success.
    """
    # Group by category
    by_cat: dict[str, list[str]] = {}
    for c in conventions[:20]:
        cat = c.get("category", "style")
        by_cat.setdefault(cat, []).append(c.get("rule", ""))

    sections = []
    for cat, rules in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        lines = "\n".join(f"• {r[:80]}" for r in rules[:5])
        if len(rules) > 5:
            lines += f"\n_…and {len(rules) - 5} more_"
        sections.append(f"*{cat}* ({len(rules)})\n{lines}")

    body = "\n\n".join(sections)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📚 {agent_name} learned {total_count} conventions from your codebase"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Here are the top patterns I extracted. React with ❌ on any that are wrong — I'll suppress them permanently.",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "View all conventions at /dashboard/conventions. You can edit or suppress any rule there.",
                }
            ],
        },
    ]

    fallback = f"{agent_name} learned {total_count} conventions from your codebase. Review them at /dashboard/conventions."
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload: dict = {"channel": channel_id, "text": fallback, "blocks": blocks}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)

    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] post_conventions_review failed: {data.get('error')}")
        return None

    logger.info(f"[Slack] Posted conventions review to {channel_id}")
    return data.get("ts")
