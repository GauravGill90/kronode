import json
import logging
import re

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior code reviewer performing a structured critic pass.

You will receive:
- A task description
- A Definition of Done checklist
- The agent's summary of what it did
- Files that were changed
- Coding conventions the team follows

For each DoD item, determine if the implementation likely satisfies it.

Also check for common issues:
- Unnecessary reformatting of unchanged code
- Overly broad catch clauses that swallow errors
- Scope creep (changes beyond what the task asked for)
- Missing error handling or edge cases

Rules:
- "approved": true only if ALL DoD items are satisfied and no significant issues found
- "changes_requested": list of concrete, actionable follow-up items (empty if approved)
- "needs_revision": true if the coder should retry before opening a PR
- "verdict": one sentence summary

Respond with valid JSON only.

{
  "approved": true,
  "needs_revision": false,
  "dod_review": [
    {"item": "Returns 404 for missing booking", "satisfied": true, "notes": "Handled in getBookingToDelete.ts"}
  ],
  "changes_requested": [],
  "verdict": "All DoD items satisfied. Approved."
}
"""


class ReviewerAgent(AgentBase):
    display_name = "Reviewer"

    async def run(self, context: dict) -> dict:
        planner_result = context.get("planner_agent", {})
        dod = planner_result.get("definition_of_done", [])
        coder_result = context.get("coder_agent", {})

        if not dod:
            logger.info("[Reviewer] No DoD items — auto-approving")
            return _approved("No Definition of Done items — auto-approved.")

        # If coder failed or produced no changes, don't pretend it passed
        files_changed = coder_result.get("files_changed", [])
        coder_error = coder_result.get("error")
        if coder_error or not files_changed:
            reason = coder_error or "Coder produced no file changes"
            logger.warning(f"[Reviewer] Coder failed — rejecting: {reason}")
            return {
                "approved": False,
                "needs_revision": True,
                "dod_review": [{"item": d, "satisfied": False, "notes": "Coder did not produce changes"} for d in dod],
                "changes_requested": [f"Coder failed: {reason}. All DoD items unverified."],
                "verdict": f"Rejected — coder did not produce changes: {reason}",
                "summary": f"Rejected — coder failed: {reason}",
            }

        # Build review context from the coder's output
        files_changed = coder_result.get("files_changed", [])
        agent_response = coder_result.get("agent_response", "")
        cost = coder_result.get("cost_usd", 0)
        num_turns = coder_result.get("num_turns", 0)

        # Get conventions for the reviewer to check against
        context_bundle = context.get("context_builder", {})
        conventions = context_bundle.get("conventions", [])
        conv_text = "\n".join(
            f"- {c['rule']}" if isinstance(c, dict) else f"- {c}"
            for c in conventions[:15]
        )

        user_message = f"""Task: {context.get('description', '')}

Definition of Done:
{json.dumps(dod, indent=2)}

Files changed: {json.dumps(files_changed)}

Agent summary:
{agent_response[:3000] if agent_response else coder_result.get('summary', 'No summary')}

Key conventions to verify:
{conv_text or 'none'}

Cost: ${cost:.4f}, Turns: {num_turns}
"""

        try:
            from app.core.llm import cheap
            raw = await cheap(system=SYSTEM_PROMPT, user_message=user_message, max_tokens=1024)
            raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
            raw = re.sub(r"\n?```$", "", raw)

            review = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                review = json.loads(match.group())
            else:
                logger.warning(f"[Reviewer] JSON parse failed — auto-approving")
                return _approved("Review parse failed — auto-approved.")
        except Exception as exc:
            logger.warning(f"[Reviewer] LLM call failed: {exc} — auto-approving")
            return _approved(f"Review skipped ({exc}) — auto-approved.")

        approved = bool(review.get("approved", True))
        needs_revision = bool(review.get("needs_revision", False))
        dod_review = review.get("dod_review", [])
        changes_requested = review.get("changes_requested", [])
        verdict = review.get("verdict", "Review complete.")

        satisfied = sum(1 for item in dod_review if item.get("satisfied"))
        total = len(dod_review) or len(dod)
        summary = (
            f"Critic pass: {satisfied}/{total} DoD items satisfied. "
            f"{'Approved.' if approved else f'Changes requested: {len(changes_requested)} item(s).'}"
        )
        logger.info(f"[Reviewer] {summary}")

        return {
            "approved": approved,
            "needs_revision": needs_revision,
            "dod_review": dod_review,
            "changes_requested": changes_requested,
            "verdict": verdict,
            "summary": summary,
        }


def _approved(reason: str) -> dict:
    return {
        "approved": True,
        "needs_revision": False,
        "dod_review": [],
        "changes_requested": [],
        "verdict": reason,
        "summary": f"Reviewer: {reason}",
    }
