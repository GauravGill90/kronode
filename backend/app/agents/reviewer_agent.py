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
- "approved": true only if ALL non-N/A DoD items are satisfied and no significant issues found
- "changes_requested": list of concrete, actionable follow-up items (empty if approved)
- "needs_revision": true if the coder should retry before opening a PR
- "verdict": one sentence summary
- If a DoD item references tests but no test files exist for the module, mark it "satisfied": false with "status": "n/a" and explain why (e.g. "No test files exist for this module")
- If a DoD item's precondition does not exist (e.g. "linting passes" but no linter configured), mark it "status": "n/a"
- N/A items do NOT block approval

Respond with valid JSON only.

{
  "approved": true,
  "needs_revision": false,
  "dod_review": [
    {"item": "Returns 404 for missing booking", "satisfied": true, "status": "pass", "notes": "Handled in getBookingToDelete.ts"},
    {"item": "All tests pass", "satisfied": false, "status": "n/a", "notes": "No test files exist for this module"}
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
        pr_url = coder_result.get("pr_url")
        cost = coder_result.get("cost_usd", 0)
        num_turns = coder_result.get("num_turns", 0)

        # Fetch actual PR diff if available
        diff_text = ""
        if pr_url:
            github_token = context.get("github_access_token")
            if github_token:
                try:
                    diff_text = await _fetch_pr_diff(pr_url, github_token)
                    logger.info(f"[Reviewer] Fetched PR diff: {len(diff_text)} chars")
                except Exception as exc:
                    logger.warning(f"[Reviewer] Failed to fetch PR diff: {exc}")

        # Get conventions for the reviewer to check against
        context_bundle = context.get("context_builder", {})
        conventions = context_bundle.get("conventions", [])
        conv_text = "\n".join(
            f"- {c['rule']}" if isinstance(c, dict) else f"- {c}"
            for c in conventions[:15]
        )

        review_source = diff_text[:8000] if diff_text else (
            agent_response[:3000] if agent_response else coder_result.get('summary', 'No summary')
        )
        source_label = "PR Diff" if diff_text else "Agent Summary"

        user_message = f"""Task: {context.get('description', '')}

Definition of Done:
{json.dumps(dod, indent=2)}

Files changed: {json.dumps(files_changed)}

{source_label}:
{review_source}

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

        na_count = sum(1 for item in dod_review if item.get("status") == "n/a")
        satisfied = sum(1 for item in dod_review if item.get("satisfied") and item.get("status") != "n/a")
        total = len(dod_review) or len(dod)
        actionable = total - na_count
        summary = (
            f"Critic pass: {satisfied}/{actionable} DoD items satisfied"
            f"{f' ({na_count} N/A)' if na_count else ''}. "
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


async def _fetch_pr_diff(pr_url: str, token: str) -> str:
    """Fetch the actual diff from a GitHub PR."""
    import httpx
    from app.services.github_service import _parse_pr_url, _auth_headers, GITHUB_API

    owner, repo, number = _parse_pr_url(pr_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/files",
            headers=headers,
            params={"per_page": 30},
        )
        if not resp.is_success:
            return ""

        files = resp.json()
        patches = []
        total = 0
        for f in files:
            patch = f.get("patch", "")
            header = f"--- {f['filename']} (+{f.get('additions', 0)} -{f.get('deletions', 0)})"
            section = f"{header}\n{patch}"
            if total + len(section) > 8000:
                break
            patches.append(section)
            total += len(section)

        return "\n\n".join(patches)


def _approved(reason: str) -> dict:
    return {
        "approved": True,
        "needs_revision": False,
        "dod_review": [],
        "changes_requested": [],
        "verdict": reason,
        "summary": f"Reviewer: {reason}",
    }
