import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class ContextBuilderAgent(AgentBase):
    display_name = "Context Builder"

    async def run(self, context: dict) -> dict:
        logger.info("[ContextBuilder] STUB — returning empty context bundle")
        return {
            "summary": "Context bundle assembled (stub — no repo files fetched yet).",
            "relevant_files": [],
            "conventions": [],
            "pr_patterns": [],
            "memory_records": [],
        }
