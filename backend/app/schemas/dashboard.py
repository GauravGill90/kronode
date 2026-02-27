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
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    agent: AgentConfig | None
    integrations: IntegrationStatus
    recent_tasks: list[TaskSummary]
    onboarding_complete: bool
