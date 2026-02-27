import logging

logger = logging.getLogger(__name__)


async def update_ticket_status(ticket_id: str, status: str, pr_url: str | None = None) -> bool:
    """STUB — update Jira ticket status and link PR."""
    logger.info(f"[Jira] STUB — would update {ticket_id} to {status}, PR: {pr_url}")
    return True
