import json
import logging
import re

from app.agents.base import AgentBase

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

SYSTEM_PROMPT = """You are a senior software architect planning implementation for an autonomous coding agent.

Your job is to break down a task into concrete, ordered implementation steps — NOT to repeat the requirements.

Rules:
- Each subtask must be a specific coding action: "Create X component", "Add Y API endpoint", "Update Z to include..."
- Include the exact file paths to create or modify. Infer paths from the codebase context provided.
- Definition of Done must be testable assertions, not vague statements. Use the acceptance criteria from the ticket if provided.
- Flag risks: auth changes, database migrations, breaking changes, files outside guardrails.
- List assumptions: things you're inferring that haven't been confirmed.
- Do NOT just restate the ticket description as a subtask. Break it into implementation steps.

Respond with valid JSON only. No markdown, no explanation.

JSON structure:
{
  "subtasks": [
    {"order": 1, "description": "Create EventTypeDuplicateButton component in components/event-types/", "agent": "coder_agent", "files_affected": ["components/event-types/EventTypeDuplicateButton.tsx"]},
    {"order": 2, "description": "Add duplicateEventType tRPC mutation in server/routers/event-types.ts", "agent": "coder_agent", "files_affected": ["server/routers/event-types.ts"]}
  ],
  "definition_of_done": [
    "Duplicate button appears in event type card three-dot menu",
    "Clicking duplicate creates a new event type with (Copy) suffix",
    "URL slug is auto-generated and unique",
    "New event type opens in edit mode"
  ],
  "risk_flags": [
    "Database migration needed if adding new status column"
  ],
  "assumptions": [
    "Event type card already has a three-dot menu component"
  ],
  "estimated_files": 4
}
"""


class PlannerAgent(AgentBase):
    display_name = "Planner"

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

        # Use structured task from ticket interpreter if available
        interpreter = context.get("ticket_interpreter", {})
        structured_task = interpreter.get("structured_task", {})

        if structured_task.get("requirements"):
            task_block = f"Task: {structured_task.get('title', description)}\n"
            task_block += f"Type: {structured_task.get('ticket_type', 'feature')}\n"
            task_block += f"Scope: {structured_task.get('scope', 'not specified')}\n\n"
            task_block += "Requirements:\n"
            task_block += "\n".join(f"- {r}" for r in structured_task["requirements"])
            if structured_task.get("acceptance_criteria"):
                task_block += "\n\nAcceptance criteria:\n"
                task_block += "\n".join(f"- {c}" for c in structured_task["acceptance_criteria"])
        else:
            task_block = f"Task: {description}"

        # Format conventions with source attribution
        pitfalls = context_bundle.get("pitfalls", [])
        reviewer_patterns = context_bundle.get("reviewer_patterns", [])

        if conventions and isinstance(conventions[0], dict):
            conv_lines = []
            for c in conventions[:15]:
                source = f" (from {c['source_prs'][0]})" if c.get("source_prs") else ""
                layer_label = "community best practice" if c.get("layer") == "base" else "team convention"
                conv_lines.append(f"- [{layer_label}] {c['rule']}{source}")
            conventions_text = "\n".join(conv_lines)
        else:
            conventions_text = str(conventions) if conventions else "none"

        pitfalls_text = ""
        if pitfalls:
            pitfalls_text = "\n\nKnown pitfalls for these files:\n"
            pitfalls_text += "\n".join(
                f"- {p['description']} (files: {', '.join(p.get('files', []))})"
                for p in pitfalls[:5]
            )

        reviewer_text = ""
        if reviewer_patterns:
            reviewer_text = "\n\nReviewer patterns (address these proactively):\n"
            for p in reviewer_patterns[:5]:
                reviewer = p.get("reviewer", "")
                pref = p.get("preference", "")
                if reviewer:
                    reviewer_text += f"- {reviewer} typically requests: {pref}\n"
                else:
                    reviewer_text += f"- {pref}\n"

        user_message = f"""{task_block}
{clarification_block}
Project context:
{project_context}

Relevant files (paths only):
{file_paths or "none"}

Conventions:
{conventions_text}
{pitfalls_text}
{reviewer_text}
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

        from app.core.llm import quality
        raw = await quality(system=effective_system, user_message=user_message, max_tokens=2048)

        plan = _extract_json(raw)
        if plan is None:
            logger.warning(f"PlannerAgent: failed to parse JSON response. Raw (first 300): {raw[:300]}")
            plan = {
                "subtasks": [{"order": 1, "description": description, "agent": "coder_agent", "files_affected": []}],
                "definition_of_done": ["Implementation complete", "No regressions introduced"],
                "risk_flags": [],
                "estimated_files": 1,
            }

        # Calculate confidence score based on available signals
        plan["confidence_score"] = _calculate_confidence(plan, context_bundle, context)
        if plan["confidence_score"] >= 0.7:
            plan["confidence_level"] = "high"
        elif plan["confidence_score"] >= 0.4:
            plan["confidence_level"] = "medium"
        else:
            plan["confidence_level"] = "low"

        plan["summary"] = (
            f"Plan created: {len(plan.get('subtasks', []))} subtasks, "
            f"{len(plan.get('definition_of_done', []))} DoD items. "
            f"Confidence: {plan['confidence_level']} ({plan['confidence_score']:.1f})."
        )
        return plan


def _calculate_confidence(plan: dict, context_bundle: dict, context: dict) -> float:
    """Score 0.0-1.0 based on how well-understood the task is.

    Scoring philosophy:
    - Start at 0.5 (neutral — we know nothing yet)
    - Boost for positive signals (conventions, known files, structured task, simple complexity)
    - Penalise for negative signals (risk flags, unknown files, complex task)
    - Most tasks with a connected repo and some conventions should land at 0.6-0.8
    """
    score = 0.5

    # ── Positive signals ──────────────────────────────────────────────

    # Conventions available (org has learned patterns)
    conventions = context_bundle.get("conventions", [])
    if len(conventions) >= 10:
        score += 0.15
    elif len(conventions) >= 3:
        score += 0.1
    elif conventions:
        score += 0.05

    # Files were fetched from repo (context builder worked)
    relevant_files = context_bundle.get("relevant_files", [])
    if len(relevant_files) >= 5:
        score += 0.1
    elif relevant_files:
        score += 0.05

    # Structured task from ticket interpreter (better input)
    interpreter = context.get("ticket_interpreter", {})
    structured = interpreter.get("structured_task", {})
    if structured.get("requirements"):
        score += 0.05
    if structured.get("acceptance_criteria"):
        score += 0.05

    # Simple complexity
    routing = context.get("routing", {})
    if routing.get("complexity") == "simple":
        score += 0.1

    # Pitfalls and reviewer patterns available (more context)
    if context_bundle.get("pitfalls"):
        score += 0.05
    if context_bundle.get("reviewer_patterns"):
        score += 0.05

    # ── Negative signals ──────────────────────────────────────────────

    # Risk flags from the planner
    risk_flags = plan.get("risk_flags", [])
    score -= min(len(risk_flags) * 0.05, 0.15)  # cap penalty at 0.15

    # Unknown files (planned but not in context)
    known_paths = {f["path"] for f in relevant_files}
    planned_files = set()
    for st in plan.get("subtasks", []):
        planned_files.update(st.get("files_affected", []))
    if planned_files:
        unknown_ratio = len(planned_files - known_paths) / len(planned_files)
        score -= unknown_ratio * 0.1  # softer penalty

    # Complex task
    if routing.get("complexity") == "complex":
        score -= 0.1

    return max(0.0, min(1.0, round(score, 2)))
