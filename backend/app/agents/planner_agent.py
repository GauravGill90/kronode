import json
import logging

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software architect. Your job is to create a detailed implementation plan for a development task.

You will be given:
- A task description
- Project context (tech stack, conventions)
- Codebase context (relevant files found)

Produce a structured plan with:
1. An ordered list of subtasks
2. A Definition of Done checklist
3. Risk flags

Respond with valid JSON only. No markdown, no explanation.

JSON structure:
{
  "subtasks": [
    {"order": 1, "description": "...", "agent": "coder_agent", "files_affected": ["path/to/file.tsx"]}
  ],
  "definition_of_done": [
    "UI implemented and matches design",
    "API integrated with error states handled",
    "Unit tests written and passing",
    "No hardcoded values"
  ],
  "risk_flags": [
    "Requires auth module access — confirm guardrails allow this"
  ],
  "estimated_files": 3
}
"""


class PlannerAgent(AgentBase):
    display_name = "Planner"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: dict) -> dict:
        description = context["description"]
        project_context = context.get("project_context", "No project context provided.")
        context_bundle = context.get("context_builder", {})
        relevant_files = context_bundle.get("relevant_files", [])
        conventions = context_bundle.get("conventions", [])

        user_message = f"""Task: {description}

Project context:
{project_context}

Relevant files found: {relevant_files or "none"}
Conventions: {conventions or "none"}
"""

        message = await self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = message.content[0].text.strip()
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("PlannerAgent: failed to parse JSON response")
            plan = {
                "subtasks": [{"order": 1, "description": description, "agent": "coder_agent", "files_affected": []}],
                "definition_of_done": ["Implementation complete", "No regressions introduced"],
                "risk_flags": [],
                "estimated_files": 1,
            }

        plan["summary"] = (
            f"Plan created: {len(plan.get('subtasks', []))} subtasks, "
            f"{len(plan.get('definition_of_done', []))} DoD items."
        )
        return plan
