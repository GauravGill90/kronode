import logging

logger = logging.getLogger(__name__)


async def post_notification(channel_id: str, message: str, blocks: list | None = None) -> bool:
    """STUB — post a message to a Slack channel."""
    logger.info(f"[Slack] STUB — would post to {channel_id}: {message}")
    return True
