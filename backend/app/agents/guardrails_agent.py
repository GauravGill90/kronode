import logging
from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class GuardrailsAgent(AgentBase):
    display_name = "Guardrails"

    async def run(self, context: dict) -> dict:
        logger.info("[Guardrails] STUB — always passing")
        guardrails = context.get("guardrails", {})
        restricted = guardrails.get("restricted_paths", [])
        risk_level = guardrails.get("risk_level", "balanced")
        return {
            "summary": f"Guardrails passed. Risk level: {risk_level}. Restricted paths: {restricted or 'none'}.",
            "blocked": False,
            "risk_classification": "low",
            "pr_size_estimate": "small",
        }
