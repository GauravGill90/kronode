import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from Claude's response."""
    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip a single markdown fence (```json ... ```)
    stripped = re.sub(r"^```[a-z]*\n?", "", text.strip())
    stripped = re.sub(r"\n?```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 3. Find the first { ... } block in the text (handles prose before/after JSON)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


SYSTEM_PROMPT = """You are an expert software engineer. Your job is to implement code for a given task.

You will receive:
- A task description
- An implementation plan with subtasks
- A Definition of Done checklist
- Project context (tech stack, conventions)

Rules:
- NEVER write directly to main — always create a branch
- Always write COMPLETE file contents, never partial snippets
- Write PR descriptions for a non-technical audience
- If you cannot fully satisfy a DoD item, flag it explicitly
- Branch names must follow kebab-case: feature/task-description-slug

Respond with valid JSON only. No markdown code blocks, no explanation outside the JSON.

JSON structure:
{
  "branch_name": "feature/...",
  "files": [
    {"path": "src/components/Example.tsx", "content": "full file content here"}
  ],
  "commit_message": "...",
  "pr_title": "...",
  "pr_description": "Plain English description of what changed and why, written for a non-technical reader.",
  "slack_summary": "One sentence for stakeholders.",
  "incomplete_dod_items": []
}
"""


class CoderAgent(AgentBase):
    display_name = "Coder"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: dict) -> dict:
        description = context["description"]
        project_context = context.get("project_context", "No project context provided.")
        plan = context.get("planner_agent", {})
        subtasks = plan.get("subtasks", [])
        dod = plan.get("definition_of_done", [])
        context_bundle = context.get("context_builder", {})
        relevant_files = context_bundle.get("relevant_files", [])
        conventions = context_bundle.get("conventions", [])
        repo_structure = context_bundle.get("repo_structure", "")

        # Format relevant files for the prompt
        files_section = "none — implement fresh"
        if relevant_files:
            files_section = "\n\n".join(
                f"### {f['path']}\n```\n{f['content']}\n```"
                for f in relevant_files
            )

        user_message = f"""Task: {description}

Project context:
{project_context}

Repository structure: {repo_structure or "unknown"}

Coding conventions to follow:
{json.dumps(conventions, indent=2) if conventions else "none extracted"}

Implementation plan:
{json.dumps(subtasks, indent=2)}

Definition of Done:
{json.dumps(dod, indent=2)}

Relevant existing files:
{files_section}
"""

        if settings.bypass_llm:
            logger.info("CoderAgent: BYPASS_LLM=true — skipping LLM, using hardcoded test payload")
            slug = re.sub(r"[^a-z0-9]+", "-", description[:40].lower()).strip("-")
            result = {
                "branch_name": f"feature/bypass-test-{slug}",
                "files": [
                    {
                        "path": "kronode_bypass_test.md",
                        "content": f"# Kronode bypass test\n\nTask: {description}\n\nThis file was created by the bypass-LLM test mode to verify the GitHub PR pipeline works end-to-end without an LLM call.\n",
                    }
                ],
                "commit_message": f"test: bypass LLM PR test — {description[:60]}",
                "pr_title": f"[bypass] {description[:70]}",
                "pr_description": "This PR was opened by Kronode's bypass-LLM test mode. No LLM was involved — the GitHub integration pipeline is being verified.",
                "slack_summary": f"Bypass test PR opened for: {description[:100]}",
                "incomplete_dod_items": [],
            }
        else:
            message = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            stop_reason = message.stop_reason
            raw = message.content[0].text.strip()
            logger.info(f"CoderAgent stop_reason={stop_reason} response_len={len(raw)} chars")
            if stop_reason == "max_tokens":
                logger.warning("CoderAgent: response was TRUNCATED (max_tokens hit) — JSON will be incomplete")
            logger.info(f"CoderAgent raw response (first 500 chars): {raw[:500]}")

            result = _extract_json(raw)
            if result is None:
                logger.warning(f"CoderAgent: failed to parse JSON. Full response:\n{raw}")
                result = {
                    "branch_name": "feature/task-implementation",
                    "files": [],
                    "commit_message": f"Implement: {description[:72]}",
                    "pr_title": description[:70],
                    "pr_description": description,
                    "slack_summary": f"Agent completed: {description[:100]}",
                    "incomplete_dod_items": ["JSON parse failed — review agent output manually"],
                }

        # Attempt to create the PR via GitHub service
        repo_url = context.get("repo_url", "")
        github_token = context.get("github_access_token")
        if repo_url and github_token and result.get("files"):
            try:
                from app.services.github_service import create_pull_request
                pr_url = await create_pull_request(
                    repo_url=repo_url,
                    branch_name=result["branch_name"],
                    files=result["files"],
                    commit_message=result["commit_message"],
                    pr_title=result["pr_title"],
                    pr_description=result["pr_description"],
                    token=github_token,
                )
                result["pr_url"] = pr_url
            except Exception as exc:
                logger.warning(f"CoderAgent: GitHub PR creation failed: {exc}")
                result["pr_url"] = None
                result["github_error"] = str(exc)
        elif repo_url and not github_token:
            logger.warning("CoderAgent: skipping PR — no GitHub token configured")
            result["pr_url"] = None
            result["github_error"] = "No GitHub token configured. Add a PAT in onboarding."

        result["summary"] = (
            f"Code written: {len(result.get('files', []))} file(s). "
            f"Branch: {result.get('branch_name', 'N/A')}. "
            f"PR: {result.get('pr_url', 'pending')}."
        )
        return result
