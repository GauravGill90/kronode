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
    email: str
    api_token: str
    status_mappings: dict[str, Any] | None = None


class SlackPayload(BaseModel):
    channel_id: str
    channel_name: str
    bot_token: str


class SlackTestPayload(BaseModel):
    bot_token: str
    channel_name: str


class JiraTestPayload(BaseModel):
    workspace_url: str
    project_key: str
    email: str
    api_token: str


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


class GitHubTokenPayload(BaseModel):
    token: str


class GitHubTokenTestPayload(BaseModel):
    token: str
    repo_url: str


class OnboardingStatus(BaseModel):
    completed: bool
    current_step: int
    agent_name: str | None = None


class OnboardingConfigOut(BaseModel):
    """Full config returned to the frontend for store hydration."""
    # agent
    agent_name: str | None = None
    agent_avatar: str | None = None
    # repo
    repo_url: str | None = None
    repo_provider: str | None = None
    repo_name: str | None = None
    has_github_token: bool = False
    # capabilities + guardrails (raw JSONB blobs)
    capabilities: dict | None = None
    guardrails: dict | None = None
    # project context
    project_context: str | None = None
    # account (from user + org)
    user_name: str | None = None
    user_role: str | None = None
    company_name: str | None = None
    # jira
    jira_workspace_url: str | None = None
    jira_project_key: str | None = None
    jira_email: str | None = None
    has_jira_token: bool = False
    # slack
    slack_channel_id: str | None = None
    slack_channel_name: str | None = None
    has_slack_token: bool = False
