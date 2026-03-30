from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    github: bool = False
    jira: bool = False
    slack: bool = False
    docs: bool = False


class AgentConfig(BaseModel):
    agent_name: str
    agent_avatar: str
    capabilities: dict[str, Any] | None = None
    guardrails: dict[str, Any] | None = None


class TaskSummary(BaseModel):
    id: uuid.UUID
    description: str
    status: str
    pr_url: str | None = None
    cost_usd: float | None = None
    num_turns: int | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PRStats(BaseModel):
    total_prs: int = 0
    merged: int = 0
    in_review: int = 0
    rejected: int = 0
    failed: int = 0
    acceptance_rate: float | None = None  # merged / (merged + rejected), None if no data
    avg_cost_usd: float | None = None
    avg_turns: float | None = None


class DashboardOut(BaseModel):
    user_name: str | None
    agent: AgentConfig | None
    integrations: IntegrationStatus
    recent_tasks: list[TaskSummary]
    pr_stats: PRStats = PRStats()
    onboarding_complete: bool
