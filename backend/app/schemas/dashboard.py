"""Dashboard response schemas — organizational memory platform view."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntegrationDetail(BaseModel):
    connected: bool = False
    provider: str = ""
    name: str = ""  # repo name, project key, channel name, etc.


class IntegrationsStatus(BaseModel):
    git: IntegrationDetail = IntegrationDetail()
    docs: IntegrationDetail = IntegrationDetail()
    issues: IntegrationDetail = IntegrationDetail()
    slack: IntegrationDetail = IntegrationDetail()


class MCPTool(BaseModel):
    name: str
    description: str


class ActivityItem(BaseModel):
    action: str
    resource: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime


class ConventionSummary(BaseModel):
    id: int
    rule: str
    category: str
    confidence: float
    enforced_by: list[str] | None = None


class DocSourceSummary(BaseModel):
    source_type: str
    source_count: int  # unique source_refs
    chunk_count: int
    last_updated: datetime | None = None


class DashboardOut(BaseModel):
    org_name: str = ""
    user_name: str | None = None
    onboarding_complete: bool = False

    # Stats
    convention_count: int = 0
    enforced_convention_count: int = 0
    doc_chunk_count: int = 0
    doc_source_count: int = 0
    reviewer_pattern_count: int = 0
    failure_count: int = 0
    active_api_key_count: int = 0
    mcp_calls_this_month: int = 0

    # Integrations
    integrations: IntegrationsStatus = IntegrationsStatus()

    # MCP tools
    mcp_tools: list[MCPTool] = []

    # Recent activity
    recent_activity: list[ActivityItem] = []

    # Top conventions
    top_conventions: list[ConventionSummary] = []

    # Doc sources
    doc_sources: list[DocSourceSummary] = []


# Keep backward compat aliases for old code that imports these
class IntegrationStatus(BaseModel):
    github: bool = False
    jira: bool = False
    slack: bool = False
    docs: bool = False


class AgentConfig(BaseModel):
    agent_name: str = ""
    agent_avatar: str = ""
    capabilities: dict[str, Any] | None = None
    guardrails: dict[str, Any] | None = None


class TaskSummary(BaseModel):
    id: str = ""
    description: str = ""
    status: str = ""
    pr_url: str | None = None
    cost_usd: float | None = None
    num_turns: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PRStats(BaseModel):
    total_prs: int = 0
    merged: int = 0
    in_review: int = 0
    rejected: int = 0
    failed: int = 0
    acceptance_rate: float | None = None
    avg_cost_usd: float | None = None
    avg_turns: float | None = None
