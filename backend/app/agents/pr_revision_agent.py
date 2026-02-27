import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

TRIAGE_PROMPT = """You are reviewing GitHub PR feedback to decide whether the requested changes are clear enough to implement.

Given a list of review comments and inline code comments, decide:
- If ALL comments are specific and actionable → {"actionable": true, "questions": []}
- If ANY comment is vague or ambiguous → {"actionable": false, "questions": ["specific question 1", ...]}

Max 2 questions. Each question must target a specific unclear comment.
Respond with valid JSON only. No markdown, no explanation.
"""

REVISION_PROMPT = """You are a software engineer addressing PR review feedback.

You will receive:
- The original task description
- The files that were written (current state of the code on the branch)
- Review comments (reviewer's overall feedback)
- Inline code comments (file-specific, line-level feedback)

Your job is to produce updated versions of the affected files that address all reviewer feedback.

Rules:
- Return COMPLETE file contents, never partial diffs or snippets
- Only include files that need to change — do not return unchanged files
- If a review comment requires deleting code, remove it entirely
- Address every comment. If a comment is contradictory, note it in the commit message.

Respond with valid JSON only. No markdown code blocks.

{
  "files": [
    {"path": "src/...", "content": "full updated file content"}
  ],
  "commit_message": "fix: address PR review — <short summary of changes>",
  "summary": "One sentence describing what was fixed."
}
"""


def _extract_json(text: str) -> dict | None:
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


class PRRevisionAgent(AgentBase):
    display_name = "PR Revision"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: dict) -> dict:
        review_comments: list[str] = context.get("review_comments", [])
        inline_comments: list[dict] = context.get("inline_comments", [])
        original_files: list[dict] = context.get("original_files", [])
        description = context.get("description", "")
        pr_url = context.get("pr_url", "")

        if not review_comments and not inline_comments:
            return {"summary": "No review comments to address.", "files": []}

        # ── Step 1: Haiku triage — actionable or needs clarification ──────────
        all_comments = "\n".join(f"- {c}" for c in review_comments)
        for ic in inline_comments:
            all_comments += f"\n- [{ic['path']}] {ic['body']}"

        triage_message = (
            f"PR: {pr_url}\n\nReview comments:\n{all_comments}"
        )

        actionable = True
        questions: list[str] = []
        try:
            resp = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=TRIAGE_PROMPT,
                messages=[{"role": "user", "content": triage_message}],
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            actionable = bool(parsed.get("actionable", True))
            questions = parsed.get("questions", [])
        except Exception as exc:
            logger.warning(f"[PRRevision] Triage call failed: {exc} — assuming actionable")

        # ── Step 2a: Not actionable → post Slack questions ────────────────────
        if not actionable and questions:
            slack_token = context.get("slack_bot_token")
            slack_channel = context.get("slack_channel_id")
            agent_name = context.get("agent_name", "Kronode")
            task_id = context.get("task_id", "unknown")

            if slack_token and slack_channel:
                try:
                    from app.services.slack_service import post_clarification
                    result = await post_clarification(
                        channel_id=slack_channel,
                        questions=questions,
                        task_id=task_id,
                        agent_name=agent_name,
                        bot_token=slack_token,
                    )
                    if result:
                        thread_ts, real_channel_id = result
                        logger.info(
                            f"[PRRevision] Posted {len(questions)} clarifying question(s) "
                            f"about PR comments to Slack (thread_ts={thread_ts})"
                        )
                except Exception as exc:
                    logger.warning(f"[PRRevision] Slack clarification post failed: {exc}")

            return {
                "needs_clarification": True,
                "questions": questions,
                "summary": f"PR comments need clarification. Posted {len(questions)} question(s) to Slack.",
            }

        # ── Step 2b: Actionable → Sonnet produces revised files ───────────────
        files_section = "none"
        if original_files:
            files_section = "\n\n".join(
                f"### {f['path']}\n```\n{f['content']}\n```"
                for f in original_files
            )

        inline_section = "\n".join(
            f"- [{ic['path']}] {ic['body']}" for ic in inline_comments
        ) or "none"

        user_message = (
            f"Original task: {description}\n\n"
            f"PR: {pr_url}\n\n"
            f"Reviewer overall comments:\n{all_comments or 'none'}\n\n"
            f"Inline code comments:\n{inline_section}\n\n"
            f"Current files on the branch:\n{files_section}"
        )

        profile_injection = context.get("profile_injection", "")
        coding_standards = context.get("coding_standards", "")
        parts = []
        if profile_injection:
            parts.append(profile_injection)
        if coding_standards:
            parts.append(f"--- Team Coding Standards ---\n{coding_standards}")
        parts.append(REVISION_PROMPT)
        effective_system = "\n\n---\n\n".join(parts)

        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8096,
                system=[
                    {"type": "text", "text": effective_system, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": user_message}],
            )
            raw = message.content[0].text.strip()
            result = _extract_json(raw)
        except Exception as exc:
            logger.warning(f"[PRRevision] Sonnet revision call failed: {exc}")
            return {"summary": f"Revision LLM call failed: {exc}", "files": []}

        if result is None:
            logger.warning("[PRRevision] Failed to parse Sonnet JSON response")
            return {"summary": "Revision failed — could not parse LLM response.", "files": []}

        logger.info(
            f"[PRRevision] Revision complete: {len(result.get('files', []))} file(s) to update"
        )
        result["summary"] = result.get(
            "summary",
            f"Addressed PR review — {len(result.get('files', []))} file(s) updated.",
        )
        return result
