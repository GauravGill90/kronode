import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class MemoryAgent(AgentBase):
    display_name = "Memory"

    async def run(self, context: dict) -> dict:
        logger.info("[Memory] STUB — write-back not implemented yet")
        return {
            "summary": "Memory write-back skipped (stub).",
            "records_written": 0,
        }
