import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class DocAgent(AgentBase):
    display_name = "Doc Agent"

    async def run(self, context: dict) -> dict:
        logger.info("[DocAgent] STUB — document parsing not implemented yet")
        return {
            "summary": "Document processing skipped (stub).",
            "epics": [],
            "stories": [],
            "total_story_points": 0,
        }
