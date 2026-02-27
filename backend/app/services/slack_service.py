import logging

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


async def post_notification(
    channel_id: str,
    message: str,
    bot_token: str,
    blocks: list | None = None,
) -> bool:
    """Post a message to a Slack channel using a bot token (xoxb-...)."""
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
        return False

    logger.info(f"[Slack] Posted to {channel_id}: {message[:80]}")
    return True
