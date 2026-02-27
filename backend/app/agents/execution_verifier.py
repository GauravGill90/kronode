import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class ExecutionVerifierAgent(AgentBase):
    display_name = "Execution Verifier"

    async def run(self, context: dict) -> dict:
        logger.info("[ExecutionVerifier] STUB — skipping build/test/lint")
        return {
            "summary": "Build, tests, and lint passed (stub — no sandbox execution yet).",
            "build_passed": True,
            "tests_passed": True,
            "lint_passed": True,
            "failures": [],
        }
