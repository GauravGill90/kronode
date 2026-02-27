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
