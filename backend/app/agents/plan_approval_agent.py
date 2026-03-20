import logging

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


class PlanApprovalAgent(AgentBase):
    display_name = "Plan Posted"

    async def run(self, context: dict) -> dict:
        """Post the plan to Slack and Jira for visibility, then proceed immediately.

        No human approval gate — Kronode works autonomously. The plan is posted
        so the team can see what's happening, not to ask permission.
        """
        plan = context.get("planner_agent", {})
        confidence_level = plan.get("confidence_level", "medium")
        confidence_score = plan.get("confidence_score", 0.5)

        slack_token = context.get("slack_bot_token")
        slack_channel = context.get("slack_channel_id")
        agent_name = context.get("agent_name", "Kronode")
        task_id = context.get("task_id", "unknown")

        # Post plan to Slack for visibility
        if slack_token and slack_channel:
            try:
                from app.services.slack_service import post_plan_for_approval
                await post_plan_for_approval(
                    channel_id=slack_channel,
                    plan=plan,
                    task_id=task_id,
                    agent_name=agent_name,
                    confidence_level=confidence_level,
                    confidence_score=confidence_score,
                    bot_token=slack_token,
                )
            except Exception as exc:
                logger.warning(f"[PlanPosted] Slack post failed: {exc}")

        # Post plan to Jira as a comment
        jira_ticket_id = context.get("jira_ticket_id")
        jira_workspace = context.get("jira_workspace_url")
        jira_email = context.get("jira_email")
        jira_token = context.get("jira_api_token")
        if jira_ticket_id and jira_workspace and jira_email and jira_token:
            try:
                from app.services.jira_service import post_plan_comment
                await post_plan_comment(
                    workspace_url=jira_workspace,
                    email=jira_email,
                    api_token=jira_token,
                    ticket_id=jira_ticket_id,
                    plan=plan,
                    confidence_level=confidence_level,
                    confidence_score=confidence_score,
                    agent_name=agent_name,
                )
            except Exception as exc:
                logger.warning(f"[PlanPosted] Jira comment failed: {exc}")

        # No waiting — proceed immediately
        return {
            "approved": True,
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "summary": f"Plan posted to Slack/Jira for visibility. Confidence: {confidence_level} ({confidence_score:.1f}). Proceeding.",
        }
