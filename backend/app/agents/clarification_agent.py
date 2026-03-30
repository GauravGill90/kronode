import json
import logging
import re

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task clarification assistant for an autonomous AI developer agent.

Given a task description and project context, decide whether the task is ambiguous enough
to require clarification before work begins.

Rules:
- Default to NOT asking. Most tasks are clear enough to start. Bias heavily toward {"needs_clarification": false}.
- Only ask when the task CANNOT be started without an answer — e.g. the target file/module is unclear, or two valid interpretations would lead to completely different implementations.
- NEVER ask about hypothetical edge cases, future extensibility, or "what if" scenarios. The agent can handle edge cases with sensible defaults.
- NEVER ask about things that can be inferred from the codebase (e.g. "what branch naming convention?" — just read the code).
- NEVER ask about multiple linked tickets, all branch types, or naming conventions unless the task is specifically about those topics and the answer is genuinely ambiguous.
- Maximum 2 questions. Each must be specific, actionable, and blocking.
- Respond with valid JSON only. No markdown, no explanation outside the JSON.

Examples of when NOT to ask:
- "Include Jira ID in branch name" → clear, just do it, fall back gracefully if no ID
- "Replace raw status codes with constants" → clear, mechanical refactor
- "Fix the login button color" → clear, find and fix it

Examples of when to ask:
- "Refactor the auth system" → which auth system? There are two (JWT + OAuth)
- "Add a new API endpoint" → for what resource? No details given
"""


class ClarificationAgent(AgentBase):
    display_name = "Clarification"

    async def run(self, context: dict) -> dict:
        # Skip for simple tasks (router fast-path already handles them)
        routing = context.get("routing", {})
        if routing.get("complexity") == "simple":
            logger.info("[Clarification] Simple task — skipping")
            return _skip("Simple task — clarification not needed.")

        # Skip if we already have a clarification answer (pipeline resumed after first round)
        if context.get("clarification_answer"):
            logger.info("[Clarification] Already have answer — skipping second round")
            return _skip("Clarification already provided — skipping.")

        slack_token = context.get("slack_bot_token")
        slack_channel = context.get("slack_channel_id")
        if not slack_token or not slack_channel:
            logger.info("[Clarification] No Slack config — skipping")
            return _skip("No Slack config — clarification skipped.")

        # If ticket_interpreter already identified ambiguities, use those directly
        interpreter = context.get("ticket_interpreter", {})
        structured_task = interpreter.get("structured_task", {})
        interpreter_ambiguities = structured_task.get("ambiguities", [])

        if interpreter_ambiguities:
            # Filter out non-blocking ambiguities — only keep genuinely blocking ones
            blocking_keywords = ["which", "what module", "what resource", "conflicting", "two valid", "unclear target"]
            filtered = [
                q for q in interpreter_ambiguities
                if any(kw in q.lower() for kw in blocking_keywords)
            ]
            if filtered:
                logger.info(f"[Clarification] {len(filtered)} blocking ambiguity(ies) from interpreter (filtered from {len(interpreter_ambiguities)})")
                needs_clarification = True
                questions = filtered[:2]
            else:
                logger.info(f"[Clarification] {len(interpreter_ambiguities)} interpreter ambiguity(ies) filtered out — none blocking")
                needs_clarification = False
                questions = []
        else:
            # Fall back to LLM-based ambiguity detection
            description = context.get("description", "")
            project_context = context.get("project_context", "")
            context_summary = context.get("context_builder", {}).get("summary", "")

            user_message = (
                f"Task: {description}\n\n"
                f"Project context: {project_context or 'none provided'}\n\n"
                f"Relevant codebase summary: {context_summary or 'none available'}"
            )

            needs_clarification = False
            questions = []

            try:
                from app.core.llm import cheap
                raw = await cheap(system=SYSTEM_PROMPT, user_message=user_message, max_tokens=256)
                raw = re.sub(r"\n?```$", "", raw)
                parsed = json.loads(raw)
                needs_clarification = bool(parsed.get("needs_clarification", False))
                questions = parsed.get("questions", [])
            except Exception as exc:
                logger.warning(f"[Clarification] LLM call failed: {exc} — skipping clarification")
                return _skip(f"LLM call failed ({exc}) — skipping.")

        if not needs_clarification or not questions:
            logger.info("[Clarification] Task is clear — no questions needed")
            return _skip("Task intent is clear — no clarification needed.")

        # Post questions to Slack
        task_id = context.get("task_id", "unknown")
        agent_name = context.get("agent_name", "Kronode")

        try:
            from app.services.slack_service import post_clarification
            result = await post_clarification(
                channel_id=slack_channel,
                questions=questions,
                task_id=task_id,
                agent_name=agent_name,
                bot_token=slack_token,
            )
        except Exception as exc:
            logger.warning(f"[Clarification] Slack post failed: {exc} — skipping clarification")
            return _skip(f"Slack post failed ({exc}) — skipping.")

        if not result:
            logger.warning("[Clarification] Slack returned no ts — skipping clarification")
            return _skip("Slack post returned no thread ts — skipping.")

        thread_ts, real_channel_id = result
        logger.info(f"[Clarification] Posted {len(questions)} question(s) to Slack, channel={real_channel_id} thread_ts={thread_ts}")
        return {
            "waiting": True,
            "thread_ts": thread_ts,
            "slack_channel_id": real_channel_id,  # real ID (C0XXXXXXX), not the name
            "questions": questions,
            "needs_clarification": True,
            "summary": f"Posted {len(questions)} clarifying question(s) to Slack. Waiting for reply.",
        }


def _skip(reason: str) -> dict:
    return {
        "summary": reason,
        "questions": [],
        "needs_clarification": False,
    }
