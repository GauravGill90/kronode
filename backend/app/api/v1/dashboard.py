"""Dashboard endpoint — organizational memory platform overview."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import Organization, OnboardingConfig
from app.models.user import User
from app.models.convention import Convention
from app.models.doc_chunk import DocChunk
from app.models.memory import MemoryRecord
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.schemas.dashboard import (
    DashboardOut, IntegrationsStatus, IntegrationDetail,
    MCPTool, ActivityItem, ConventionSummary, DocSourceSummary,
)

router = APIRouter()

# MCP tools registry — these are the tools available via the MCP server
MCP_TOOLS = [
    MCPTool(name="get_context", description="Get ranked conventions, pitfalls, reviewer patterns, and docs for a coding task"),
    MCPTool(name="get_doc", description="Search and return full documentation pages by title or keyword"),
    MCPTool(name="get_file_companions", description="Find files that typically change together based on git history"),
    MCPTool(name="get_reviewer_guidance", description="Get per-reviewer preferences for files being changed"),
    MCPTool(name="check_completeness", description="Check if any companion files were missed before committing"),
]


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Resolve user + org
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()

    if not user or not user.org_id:
        return DashboardOut()

    org_id = user.org_id

    # Load org + config
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    config = (await db.execute(select(OnboardingConfig).where(OnboardingConfig.org_id == org_id))).scalar_one_or_none()

    # ── Stats ────────────────────────────────────────────────────────────────

    # Conventions
    convention_count = (await db.execute(
        select(func.count(Convention.id)).where(
            Convention.org_id == org_id,
            Convention.suppressed == False,  # noqa: E712
        )
    )).scalar() or 0

    enforced_count = (await db.execute(
        select(func.count(Convention.id)).where(
            Convention.org_id == org_id,
            Convention.enforced_by.isnot(None),
            Convention.suppressed == False,  # noqa: E712
        )
    )).scalar() or 0

    # Doc chunks
    doc_chunk_count = (await db.execute(
        select(func.count(DocChunk.id)).where(DocChunk.org_id == org_id)
    )).scalar() or 0

    doc_source_count = (await db.execute(
        select(func.count(distinct(DocChunk.source_type))).where(DocChunk.org_id == org_id)
    )).scalar() or 0

    # Reviewer patterns
    reviewer_pattern_count = (await db.execute(
        select(func.count(MemoryRecord.id)).where(
            MemoryRecord.org_id == org_id,
            MemoryRecord.record_type == "pattern",
        )
    )).scalar() or 0

    # Failures
    failure_count = (await db.execute(
        select(func.count(MemoryRecord.id)).where(
            MemoryRecord.org_id == org_id,
            MemoryRecord.record_type == "coder_failure",
        )
    )).scalar() or 0

    # API keys
    api_key_count = (await db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.org_id == org_id)
    )).scalar() or 0

    # MCP calls this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mcp_calls = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.org_id == org_id,
            AuditLog.action == "mcp_tool_call",
            AuditLog.created_at >= month_start,
        )
    )).scalar() or 0

    # ── Integrations ─────────────────────────────────────────────────────────

    integrations = IntegrationsStatus()
    if config:
        integrations.git = IntegrationDetail(
            connected=bool(config.repo_url and config.github_access_token),
            provider=config.repo_provider or "github",
            name=config.repo_name or config.repo_url or "",
        )
        integrations.docs = IntegrationDetail(
            connected=bool(config.docs_provider),
            provider=config.docs_provider or "",
            name=config.docs_scope or "",
        )
        integrations.issues = IntegrationDetail(
            connected=bool(config.jira_project_key),
            provider="jira" if config.jira_project_key else "",
            name=config.jira_project_key or "",
        )
        integrations.slack = IntegrationDetail(
            connected=bool(config.slack_channel_id),
            provider="slack",
            name=config.slack_channel_id or "",
        )

    # ── Recent Activity ──────────────────────────────────────────────────────

    activity_rows = (await db.execute(
        select(AuditLog).where(
            AuditLog.org_id == org_id,
        ).order_by(AuditLog.created_at.desc()).limit(20)
    )).scalars().all()

    recent_activity = [
        ActivityItem(
            action=a.action,
            resource=a.resource,
            details=a.details,
            timestamp=a.created_at,
        )
        for a in activity_rows
    ]

    # ── Top Conventions ──────────────────────────────────────────────────────

    top_conv_rows = (await db.execute(
        select(Convention).where(
            Convention.org_id == org_id,
            Convention.suppressed == False,  # noqa: E712
        ).order_by(Convention.confidence.desc()).limit(10)
    )).scalars().all()

    top_conventions = [
        ConventionSummary(
            id=c.id,
            rule=c.rule[:300],
            category=c.category or "",
            confidence=c.confidence or 0,
            enforced_by=c.enforced_by,
        )
        for c in top_conv_rows
    ]

    # ── Doc Sources ──────────────────────────────────────────────────────────

    doc_source_rows = (await db.execute(
        select(
            DocChunk.source_type,
            func.count(distinct(DocChunk.source_ref)).label("source_count"),
            func.count(DocChunk.id).label("chunk_count"),
            func.max(DocChunk.id).label("max_id"),  # proxy for last_updated
        ).where(DocChunk.org_id == org_id)
        .group_by(DocChunk.source_type)
    )).all()

    doc_sources = [
        DocSourceSummary(
            source_type=row.source_type,
            source_count=row.source_count,
            chunk_count=row.chunk_count,
        )
        for row in doc_source_rows
    ]

    return DashboardOut(
        org_name=org.name if org else "",
        user_name=user.name,
        onboarding_complete=bool(config and config.completed_at),
        convention_count=convention_count,
        enforced_convention_count=enforced_count,
        doc_chunk_count=doc_chunk_count,
        doc_source_count=doc_source_count,
        reviewer_pattern_count=reviewer_pattern_count,
        failure_count=failure_count,
        active_api_key_count=api_key_count,
        mcp_calls_this_month=mcp_calls,
        integrations=integrations,
        mcp_tools=MCP_TOOLS,
        recent_activity=recent_activity,
        top_conventions=top_conventions,
        doc_sources=doc_sources,
    )
