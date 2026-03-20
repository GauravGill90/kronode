import json
import logging

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task router for an autonomous AI developer tool.
Your job is to classify incoming tasks and select which agents should run.

Available agents (in order):
- ticket_interpreter: parses raw ticket into structured task definition
- context_builder: assembles codebase awareness
- clarification_agent: asks questions if ambiguous
- planner_agent: creates implementation plan and DoD checklist
- plan_approval_agent: posts plan to Slack/Jira for human approval before coding
- guardrails_agent: validates scope and risk against the plan
- coder_agent: writes the code
- tester_agent: writes unit and integration tests
- execution_verifier: runs build, tests, lint
- reviewer_agent: critic pass against Definition of Done
- memory_agent: records patterns and learnings

Respond with valid JSON only. No markdown, no explanation.
"""

FEW_SHOT = """Examples:

Task: "Fix the login button color"
Response: {"agents": ["ticket_interpreter", "context_builder", "planner_agent", "guardrails_agent", "coder_agent", "reviewer_agent", "memory_agent"], "complexity": "simple", "steps": 7}

Task: "Add forgot password screen"
Response: {"agents": ["ticket_interpreter", "context_builder", "clarification_agent", "planner_agent", "plan_approval_agent", "guardrails_agent", "coder_agent", "tester_agent", "execution_verifier", "reviewer_agent", "memory_agent"], "complexity": "medium", "steps": 11}

Task: "Build full authentication system"
Response: {"agents": ["ticket_interpreter", "context_builder", "clarification_agent", "planner_agent", "plan_approval_agent", "guardrails_agent", "coder_agent", "tester_agent", "execution_verifier", "reviewer_agent", "memory_agent"], "complexity": "complex", "steps": 11}

Task: "Review PR #42"
Response: {"agents": ["context_builder", "reviewer_agent"], "complexity": "simple", "steps": 2}

Task: "Upload PRD and create tickets"
Response: {"agents": ["ticket_interpreter", "context_builder", "planner_agent", "guardrails_agent"], "complexity": "medium", "steps": 4}
"""


class RouterAgent(AgentBase):
    display_name = "Task Router"

    async def run(self, context: dict) -> dict:
        description = context["description"]

        from app.core.llm import cheap
        raw = await cheap(
            system=SYSTEM_PROMPT + "\n\n" + FEW_SHOT,
            user_message=f"Task: \"{description}\"",
            max_tokens=256,
        )
        try:
            routing = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RouterAgent: failed to parse JSON, using full pipeline fallback")
            routing = {
                "agents": [
                    "ticket_interpreter", "context_builder", "clarification_agent",
                    "planner_agent", "plan_approval_agent", "guardrails_agent",
                    "coder_agent", "tester_agent", "execution_verifier",
                    "reviewer_agent", "memory_agent"
                ],
                "complexity": "medium",
                "steps": 11,
            }

        routing["summary"] = (
            f"Task classified as {routing['complexity']}. "
            f"Running {len(routing['agents'])} agents: {', '.join(routing['agents'])}."
        )
        return routing
