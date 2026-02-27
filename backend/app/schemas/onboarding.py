from pydantic import BaseModel
from typing import Any


class AccountPayload(BaseModel):
    name: str
    company_name: str
    role: str


class RepoPayload(BaseModel):
    provider: str  # github | gitlab
    repo_url: str
    repo_name: str


class JiraPayload(BaseModel):
    workspace_url: str
    project_key: str
    status_mappings: dict[str, Any] | None = None


class SlackPayload(BaseModel):
    channel_id: str
    channel_name: str


class DocsPayload(BaseModel):
    provider: str  # confluence | gdrive
    scope: str


class CapabilitiesPayload(BaseModel):
    building: dict[str, bool]
    planning: dict[str, bool]
    review: dict[str, bool]
    communication: dict[str, bool]


class GuardrailsPayload(BaseModel):
    restricted_paths: list[str] = []
    max_files_per_task: int = 10
    risk_level: str = "balanced"  # conservative | balanced | aggressive


class AgentPayload(BaseModel):
    agent_name: str
    agent_avatar: str


class ContextPayload(BaseModel):
    project_context: str


class OnboardingStatus(BaseModel):
    completed: bool
    current_step: int
    agent_name: str | None = None
