from abc import ABC, abstractmethod


class AgentBase(ABC):
    display_name: str = "Agent"

    @abstractmethod
    async def run(self, context: dict) -> dict:
        """
        Run the agent against the current pipeline context.

        Args:
            context: Shared pipeline context dict. Contains at minimum:
                - task_id: str
                - description: str
                - org_id: int
                - project_context: str
                - repo_url: str
                - guardrails: dict
                - capabilities: dict
                - routing: dict (after RouterAgent runs)
                - planner_agent: dict (after PlannerAgent runs)
                - coder_agent: dict (after CoderAgent runs)

        Returns:
            dict with at minimum:
                - summary: str  — human-readable one-liner of what happened
            And optionally:
                - blocked: bool  — if True, pipeline pauses
                - reason: str    — why it was blocked
        """
        ...
