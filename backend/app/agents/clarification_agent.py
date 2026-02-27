import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class ClarificationAgent(AgentBase):
    display_name = "Clarification"

    async def run(self, context: dict) -> dict:
        logger.info("[Clarification] STUB — no clarification needed")
        return {
            "summary": "No clarification needed. Task intent is clear.",
            "questions": [],
            "needs_clarification": False,
        }
