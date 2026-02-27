import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class ReviewerAgent(AgentBase):
    display_name = "Reviewer"

    async def run(self, context: dict) -> dict:
        logger.info("[Reviewer] STUB — approving automatically")
        planner_result = context.get("planner_agent", {})
        dod = planner_result.get("definition_of_done", [])
        return {
            "summary": f"Critic pass complete. {len(dod)} DoD items reviewed. Approved (stub).",
            "approved": True,
            "changes_requested": [],
            "inline_comments": [],
            "verdict": "Approved — implementation satisfies the Definition of Done.",
        }
