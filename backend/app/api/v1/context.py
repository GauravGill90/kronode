"""REST API for Kronode context — for non-MCP clients (Aider, CI/CD, scripts).

Mirrors the MCP tools but via standard HTTP POST endpoints.
Auth: API key via Authorization: Bearer kron_xxx header.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Auth dependency ──────────────────────────────────────────────────────────

async def _get_org_from_api_key(authorization: str = "") -> int:
    """Extract and validate API key from Authorization header."""
    from fastapi import Header
    raise NotImplementedError("Wired below via Depends")


from fastapi import Header


async def get_org_from_api_key(authorization: str = Header("")) -> int:
    """Validate API key and return org_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:]
    try:
        from app.mcp.auth import validate_token
        api_key = await validate_token(token)
        return api_key.org_id
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── Request/Response models ──────────────────────────────────────────────────

class ContextRequest(BaseModel):
    task_description: str
    files_touched: list[str] | None = None


class DocRequest(BaseModel):
    query: str


class CompanionsRequest(BaseModel):
    file_path: str


class CompletenessRequest(BaseModel):
    task_description: str
    files_changed: list[str]


class ReviewerRequest(BaseModel):
    files_changed: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/context")
async def get_context(
    payload: ContextRequest,
    org_id: int = Depends(get_org_from_api_key),
):
    """Get organizational context for a coding task (equivalent to MCP get_context)."""
    from app.mcp.server import get_context as mcp_get_context, configure
    configure(org_id=org_id)
    result = await mcp_get_context(payload.task_description, payload.files_touched)
    return result


@router.post("/context/doc")
async def get_doc(
    payload: DocRequest,
    org_id: int = Depends(get_org_from_api_key),
):
    """Search and return full documentation page (equivalent to MCP get_doc)."""
    from app.mcp.server import get_doc as mcp_get_doc, configure
    configure(org_id=org_id)
    result = await mcp_get_doc(payload.query)
    return result


@router.post("/context/companions")
async def get_companions(
    payload: CompanionsRequest,
    org_id: int = Depends(get_org_from_api_key),
):
    """Find files that typically change together."""
    from app.mcp.server import get_context as mcp_get_context, configure
    configure(org_id=org_id)
    result = await mcp_get_context("", [payload.file_path])
    return {"file": payload.file_path, "companions": result.get("file_companions", [])}


@router.post("/context/completeness")
async def check_completeness(
    payload: CompletenessRequest,
    org_id: int = Depends(get_org_from_api_key),
):
    """Check if you missed any companion files."""
    from app.mcp.server import get_context as mcp_get_context, configure
    configure(org_id=org_id)
    result = await mcp_get_context(payload.task_description, payload.files_changed)
    return result.get("completeness", {"complete": True, "missing": []})


@router.post("/context/reviewer")
async def get_reviewer_guidance(
    payload: ReviewerRequest,
    org_id: int = Depends(get_org_from_api_key),
):
    """Get reviewer-specific preferences."""
    from app.mcp.server import get_context as mcp_get_context, configure
    configure(org_id=org_id)
    result = await mcp_get_context("", payload.files_changed)
    return {"files": payload.files_changed, "guidance": result.get("reviewer_guidance", [])}
