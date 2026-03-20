import json
import logging
import re

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task clarification assistant for an autonomous AI developer agent.

Given a task description and project context, decide whether the task is ambiguous enough
to require clarification before work begins.

Rules:
- If the task is clear and specific → {"needs_clarification": false, "questions": []}
- If the task is ambiguous or under-specified → {"needs_clarification": true, "questions": ["q1", ...]}
- Maximum 3 questions. Each question must be specific and actionable.
- Ask only what is truly necessary to start the work. Do not ask for information already in the description.
- Respond with valid JSON only. No markdown, no explanation outside the JSON.
"""


class ClarificationAgent(AgentBase):
    display_name = "Clarification"

    async def run(self, context: dict) -> dict:
        # Skip for simple tasks (router fast-path already handles them)
        routing = context.get("routing", {})
        if routing.get("complexity") == "simple":
            logger.info("[Clarification] Simple task — skipping")
            return _skip("Simple task — clarification not needed.")

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
            logger.info(f"[Clarification] Using {len(interpreter_ambiguities)} ambiguity(ies) from ticket interpreter")
            needs_clarification = True
            questions = interpreter_ambiguities[:3]  # max 3 questions
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
