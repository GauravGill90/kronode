import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

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

        user_message = f"""Task: {description}

Project context:
{project_context}

Implementation plan:
{json.dumps(subtasks, indent=2)}

Definition of Done:
{json.dumps(dod, indent=2)}

Relevant existing files: {relevant_files or "none — implement fresh"}
"""

        message = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = message.content[0].text.strip()

        # Strip markdown code blocks if Claude wrapped the response
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("CoderAgent: failed to parse JSON response")
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
        if repo_url and result.get("files"):
            try:
                from app.services.github_service import create_pull_request
                pr_url = await create_pull_request(
                    repo_url=repo_url,
                    branch_name=result["branch_name"],
                    files=result["files"],
                    commit_message=result["commit_message"],
                    pr_title=result["pr_title"],
                    pr_description=result["pr_description"],
                )
                result["pr_url"] = pr_url
            except Exception as exc:
                logger.warning(f"CoderAgent: GitHub PR creation failed: {exc}")
                result["pr_url"] = None
                result["github_error"] = str(exc)

        result["summary"] = (
            f"Code written: {len(result.get('files', []))} file(s). "
            f"Branch: {result.get('branch_name', 'N/A')}. "
            f"PR: {result.get('pr_url', 'pending')}."
        )
        return result
