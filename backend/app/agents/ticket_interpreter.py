import json
import logging
import re

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a ticket interpreter for an autonomous AI developer agent.

Given a raw task description (which may include a Jira ticket body), extract a structured task definition.

Rules:
- Extract explicit requirements from the description. Each requirement should be a single, actionable item.
- Identify what is in scope and what is out of scope.
- Extract acceptance criteria if present in the ticket.
- List ambiguities — things that are unclear or could be interpreted multiple ways. Only list GENUINE ambiguities that would block implementation. Do NOT list:
  - Edge cases or "what if" scenarios (the agent handles those with sensible defaults)
  - Questions about fallback behavior when input is missing (default: keep existing behavior)
  - Format/style questions that can be inferred from existing code
  - If the task is clear enough to start, return an empty ambiguities list.
- Classify the ticket type: bug_fix, feature, refactor, or chore.
- Estimate complexity: simple (< 3 files, clear scope), medium (3-10 files, some unknowns), complex (10+ files or significant unknowns).
- Write a clean one-line title summarising the task.

Respond with valid JSON only. No markdown, no explanation outside the JSON.

JSON structure:
{
  "title": "Clean one-line summary",
  "requirements": ["Requirement 1", "Requirement 2"],
  "scope": "What is in scope and what is not",
  "acceptance_criteria": ["Criterion 1", "Criterion 2"],
  "ambiguities": ["Ambiguity 1"],
  "ticket_type": "feature",
  "estimated_complexity": "medium"
}
"""


class TicketInterpreterAgent(AgentBase):
    display_name = "Ticket Interpreter"

    async def run(self, context: dict) -> dict:
        description = context.get("description", "")
        jira_ticket = context.get("jira_ticket")
        project_context = context.get("project_context", "")

        # Build the user message with all available context
        parts = [f"Task description:\n{description}"]

        if jira_ticket:
            meta = []
            if jira_ticket.get("issue_type"):
                meta.append(f"Type: {jira_ticket['issue_type']}")
            if jira_ticket.get("priority"):
                meta.append(f"Priority: {jira_ticket['priority']}")
            if jira_ticket.get("status"):
                meta.append(f"Status: {jira_ticket['status']}")
            if meta:
                parts.append(f"Jira metadata: {', '.join(meta)}")

        if project_context:
            parts.append(f"Project context:\n{project_context}")

        user_message = "\n\n".join(parts)

        try:
            from app.core.llm import cheap
            raw = await cheap(system=SYSTEM_PROMPT, user_message=user_message, max_tokens=1024)
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)

            structured_task = {
                "title": parsed.get("title", description[:100]),
                "requirements": parsed.get("requirements", []),
                "scope": parsed.get("scope", ""),
                "acceptance_criteria": parsed.get("acceptance_criteria", []),
                "ambiguities": parsed.get("ambiguities", []),
                "ticket_type": parsed.get("ticket_type", "feature"),
                "estimated_complexity": parsed.get("estimated_complexity", "medium"),
            }

            ambiguity_count = len(structured_task["ambiguities"])
            req_count = len(structured_task["requirements"])

            logger.info(
                f"[TicketInterpreter] Parsed: type={structured_task['ticket_type']}, "
                f"complexity={structured_task['estimated_complexity']}, "
                f"{req_count} requirements, {ambiguity_count} ambiguities"
            )

            return {
                "structured_task": structured_task,
                "raw_description": description,
                "summary": (
                    f"Interpreted: {structured_task['title']} "
                    f"({structured_task['ticket_type']}, {structured_task['estimated_complexity']}). "
                    f"{req_count} requirement(s), {ambiguity_count} ambiguity(ies)."
                ),
            }

        except Exception as exc:
            logger.warning(f"[TicketInterpreter] Failed: {exc} — passing through raw description")
            return {
                "structured_task": {
                    "title": description[:100],
                    "requirements": [],
                    "scope": "",
                    "acceptance_criteria": [],
                    "ambiguities": [],
                    "ticket_type": "feature",
                    "estimated_complexity": "medium",
                },
                "raw_description": description,
                "summary": f"Interpretation failed ({exc}) — using raw description.",
            }
