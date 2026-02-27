import json
import logging

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task router for an autonomous AI developer tool.
Your job is to classify incoming tasks and select which agents should run.

Available agents (in order):
- context_builder: assembles codebase awareness
- guardrails_agent: validates scope and risk
- clarification_agent: asks questions if ambiguous
- planner_agent: creates implementation plan and DoD checklist
- coder_agent: writes the code
- tester_agent: writes unit and integration tests
- execution_verifier: runs build, tests, lint
- reviewer_agent: critic pass against Definition of Done
- memory_agent: records patterns and learnings

Respond with valid JSON only. No markdown, no explanation.
"""

FEW_SHOT = """Examples:

Task: "Fix the login button color"
Response: {"agents": ["context_builder", "guardrails_agent", "coder_agent", "reviewer_agent", "memory_agent"], "complexity": "simple", "steps": 3}

Task: "Add forgot password screen"
Response: {"agents": ["context_builder", "guardrails_agent", "clarification_agent", "planner_agent", "coder_agent", "tester_agent", "execution_verifier", "reviewer_agent", "memory_agent"], "complexity": "medium", "steps": 9}

Task: "Build full authentication system"
Response: {"agents": ["context_builder", "guardrails_agent", "clarification_agent", "planner_agent", "coder_agent", "tester_agent", "execution_verifier", "reviewer_agent", "memory_agent"], "complexity": "complex", "steps": 9}

Task: "Review PR #42"
Response: {"agents": ["context_builder", "reviewer_agent"], "complexity": "simple", "steps": 2}

Task: "Upload PRD and create tickets"
Response: {"agents": ["context_builder", "guardrails_agent"], "complexity": "medium", "steps": 2}
"""


class RouterAgent(AgentBase):
    display_name = "Task Router"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: dict) -> dict:
        description = context["description"]

        message = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=SYSTEM_PROMPT + "\n\n" + FEW_SHOT,
            messages=[
                {"role": "user", "content": f"Task: \"{description}\""}
            ],
        )

        raw = message.content[0].text.strip()
        try:
            routing = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RouterAgent: failed to parse JSON, using full pipeline fallback")
            routing = {
                "agents": [
                    "context_builder", "guardrails_agent", "clarification_agent",
                    "planner_agent", "coder_agent", "tester_agent",
                    "execution_verifier", "reviewer_agent", "memory_agent"
                ],
                "complexity": "medium",
                "steps": 9,
            }

        routing["summary"] = (
            f"Task classified as {routing['complexity']}. "
            f"Running {len(routing['agents'])} agents: {', '.join(routing['agents'])}."
        )
        return routing
