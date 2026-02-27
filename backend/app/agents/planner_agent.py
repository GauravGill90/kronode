import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from the model response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = re.sub(r"^```[a-z]*\n?", "", text.strip())
    stripped = re.sub(r"\n?```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None

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

        # Send only file paths to the planner (not content) — coder gets the full content
        file_paths = [f["path"] for f in relevant_files] if relevant_files else []

        clarification = context.get("clarification_answer", "")
        clarification_block = (
            f"\nClarification provided by team:\n{clarification}\n"
            if clarification else ""
        )

        user_message = f"""Task: {description}
{clarification_block}
Project context:
{project_context}

Relevant files (paths only):
{file_paths or "none"}

Conventions:
{conventions or "none"}
"""

        profile_injection = context.get("profile_injection", "")
        coding_standards = context.get("coding_standards", "")

        parts = []
        if profile_injection:
            parts.append(profile_injection)
        if coding_standards:
            parts.append(f"--- Team Coding Standards ---\n{coding_standards}")
        parts.append(SYSTEM_PROMPT)
        effective_system = "\n\n---\n\n".join(parts)

        message = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=[
                {"type": "text", "text": effective_system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user_message}],
        )

        raw = message.content[0].text.strip()
        if message.stop_reason == "max_tokens":
            logger.warning("PlannerAgent: response truncated (max_tokens hit) — JSON may be incomplete")

        plan = _extract_json(raw)
        if plan is None:
            logger.warning(f"PlannerAgent: failed to parse JSON response. Raw (first 300): {raw[:300]}")
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
