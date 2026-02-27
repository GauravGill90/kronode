import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class TesterAgent(AgentBase):
    display_name = "Tester"

    async def run(self, context: dict) -> dict:
        logger.info("[Tester] STUB — skipping test generation")
        coder_result = context.get("coder_agent", {})
        files = coder_result.get("files", [])
        return {
            "summary": f"Test generation skipped (stub). {len(files)} implementation file(s) would need coverage.",
            "test_files": [],
            "coverage_summary": "No tests generated yet.",
            "untestable": [],
        }
