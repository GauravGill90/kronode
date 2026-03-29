import json
import logging
import re

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)


class CoderAgent(AgentBase):
    display_name = "Coder"

    async def run(self, context: dict) -> dict:
        description = context["description"]
        plan = context.get("planner_agent", {})
        context_bundle = context.get("context_builder", {})

        # Use fork_repo_url for writes (PRs), fall back to repo_url
        repo_url = context.get("repo_url", "")
        fork_repo_url = context.get("fork_repo_url")
        github_token = context.get("github_access_token")

        if not repo_url or not github_token:
            return {
                "summary": "Skipped — no repo or GitHub token configured.",
                "pr_url": None,
                "files_changed": [],
            }

        # Bypass mode for testing the git pipeline without LLM
        if settings.bypass_llm:
            return await self._bypass_run(description, fork_repo_url or repo_url, github_token)

        # Run Claude Agent SDK via executor
        from app.services.claude_executor import execute_task

        # Build event emitter for real-time UI updates
        task_id = context.get("task_id")
        on_event = None
        if task_id:
            from app.pipeline.pipeline import emit_event
            import uuid

            async def on_event(msg: str):
                await emit_event(uuid.UUID(task_id), "coder_agent", "progress", msg)

        # Escalate to fallback model on retry
        review_feedback = context.get("review_feedback")
        model_override = None
        if review_feedback:
            revision = review_feedback.get("revision_number", 0)
            if revision >= 1:
                model_override = settings.agent_sdk_fallback_model
                logger.info(f"CoderAgent: revision {revision} — escalating to {model_override}")

        # Cap turns for simple tasks
        complexity = context.get("routing", {}).get("complexity", "medium")
        max_turns = (
            settings.agent_sdk_max_turns_simple
            if complexity == "simple"
            else settings.agent_sdk_max_turns
        )

        result = await execute_task(
            task_description=description,
            plan=plan,
            context_bundle=context_bundle,
            repo_url=repo_url,
            fork_repo_url=fork_repo_url,
            github_token=github_token,
            profile_injection=context.get("profile_injection", ""),
            coding_standards=context.get("coding_standards", ""),
            on_event=on_event,
            review_feedback=review_feedback,
            model_override=model_override,
            max_turns=max_turns,
        )

        return result

    async def _bypass_run(self, description: str, repo_url: str, github_token: str) -> dict:
        """Bypass mode: create a test PR without LLM to verify the git pipeline."""
        logger.info("CoderAgent: BYPASS_LLM=true — creating test PR")
        slug = re.sub(r"[^a-z0-9]+", "-", description[:40].lower()).strip("-")
        branch_name = f"feature/bypass-test-{slug}"
        files = [
            {
                "path": "kronode_bypass_test.md",
                "content": f"# Kronode bypass test\n\nTask: {description}\n\nThis file was created by the bypass-LLM test mode.\n",
            }
        ]

        try:
            from app.services.github_service import create_pull_request
            pr_url = await create_pull_request(
                repo_url=repo_url,
                branch_name=branch_name,
                files=files,
                commit_message=f"test: bypass LLM PR test — {description[:60]}",
                pr_title=f"[bypass] {description[:70]}",
                pr_description="Bypass-LLM test — verifying GitHub integration pipeline.",
                token=github_token,
            )
        except Exception as exc:
            logger.warning(f"CoderAgent bypass: PR creation failed: {exc}")
            pr_url = None

        return {
            "branch_name": branch_name,
            "files_changed": ["kronode_bypass_test.md"],
            "pr_url": pr_url,
            "summary": f"Bypass test PR: {pr_url or 'failed'}",
            "slack_summary": f"Bypass test PR opened for: {description[:100]}",
            "incomplete_dod_items": [],
        }
