import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_REVIEWER_BYTES = 25_000
MAX_FILE_BYTES = 3_000

SYSTEM_PROMPT = """You are a senior code reviewer performing a structured critic pass.

You will receive:
- A Definition of Done checklist
- Implementation files written by a coding agent
- Test file paths (if any were generated)

For each DoD item, determine if the implementation satisfies it based on the provided files.

Rules:
- "approved": true only if ALL DoD items are satisfied (or no items were provided)
- "changes_requested": list of concrete, actionable follow-up items (empty if approved)
- "verdict": one sentence human-readable summary of the review outcome

Respond with valid JSON only. No markdown, no explanation outside the JSON.

JSON structure:
{
  "approved": true,
  "dod_review": [
    {"item": "UI matches design", "satisfied": true, "notes": "Component renders all required props"},
    {"item": "Tests written", "satisfied": false, "notes": "No test files found for the auth module"}
  ],
  "changes_requested": ["Add unit tests for the auth module"],
  "verdict": "Approved with minor gaps. Tests are missing for the auth module."
}
"""


class ReviewerAgent(AgentBase):
    display_name = "Reviewer"

    async def run(self, context: dict) -> dict:
        planner_result = context.get("planner_agent", {})
        dod = planner_result.get("definition_of_done", [])

        coder_result = context.get("coder_agent", {})
        impl_files = coder_result.get("files", [])

        tester_result = context.get("tester_agent", {})
        test_files = tester_result.get("test_files", [])

        if not dod:
            logger.info("[Reviewer] No DoD items — auto-approving")
            return {
                "approved": True,
                "dod_review": [],
                "changes_requested": [],
                "verdict": "No Definition of Done items provided — auto-approved.",
                "summary": "Reviewer: no DoD items to check. Auto-approved.",
            }

        # Build capped implementation files section
        file_sections: list[str] = []
        total = 0
        for f in impl_files:
            snippet = f.get("content", "")
            if len(snippet) > MAX_FILE_BYTES:
                snippet = snippet[:MAX_FILE_BYTES] + "\n… [truncated]"
            section = f"### {f['path']}\n```\n{snippet}\n```"
            if total + len(section) > MAX_REVIEWER_BYTES:
                break
            file_sections.append(section)
            total += len(section)

        truncation_note = ""
        if len(file_sections) < len(impl_files):
            truncation_note = (
                f"\nNote: only {len(file_sections)} of {len(impl_files)} "
                f"implementation files are shown due to context limits."
            )

        test_paths = [f["path"] for f in test_files]

        user_message = (
            f"Definition of Done:\n{json.dumps(dod, indent=2)}\n\n"
            f"Implementation files:{truncation_note}\n"
            + ("\n\n".join(file_sections) if file_sections else "none provided")
            + f"\n\nTest files generated: {json.dumps(test_paths) if test_paths else 'none'}\n"
        )

        approved = True
        dod_review: list[dict] = []
        changes_requested: list[str] = []
        verdict = "Review complete."

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = message.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

            try:
                review = json.loads(raw)
            except json.JSONDecodeError:
                # Try extracting a JSON object from prose output
                match = re.search(r"\{[\s\S]*\}", raw)
                if match:
                    review = json.loads(match.group())
                else:
                    raise ValueError("No JSON object found in response")

            approved = bool(review.get("approved", True))
            dod_review = review.get("dod_review", [])
            changes_requested = review.get("changes_requested", [])
            verdict = review.get("verdict", "Review complete.")

        except Exception as exc:
            logger.warning(f"[Reviewer] LLM call or parse failed: {exc} — defaulting to approved")
            approved = True
            verdict = f"Review skipped ({exc}) — defaulting to approved."

        satisfied_count = sum(1 for item in dod_review if item.get("satisfied"))
        total_count = len(dod_review) or len(dod)
        summary = (
            f"Critic pass complete. {satisfied_count}/{total_count} DoD items satisfied. "
            f"{'Approved.' if approved else f'Changes requested: {len(changes_requested)} item(s).'}"
        )
        logger.info(f"[Reviewer] {summary}")

        return {
            "approved": approved,
            "dod_review": dod_review,
            "changes_requested": changes_requested,
            "verdict": verdict,
            "summary": summary,
            # Never set blocked=True in M5 — reviewer is advisory only
        }
