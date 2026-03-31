"""API key management endpoints.

Generate, list, and revoke API keys for MCP server authentication.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.mcp.auth import generate_key
from app.models.api_key import ApiKey

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str = "default"


class CreateKeyResponse(BaseModel):
    id: int
    name: str
    key: str  # plaintext, shown ONCE
    created_at: datetime


class KeyInfo(BaseModel):
    id: int
    name: str
    key_preview: str  # first 8 + last 4 chars
    created_at: datetime
    last_used_at: datetime | None


@router.post("/api-keys", response_model=CreateKeyResponse)
async def create_api_key(
    payload: CreateKeyRequest,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. The plaintext key is returned ONCE."""
    org_id = user_data.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization found")

    plaintext, key_hash = generate_key()

    api_key = ApiKey(
        org_id=org_id,
        key_hash=key_hash,
        name=payload.name,
        created_at=datetime.now(timezone.utc),
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return CreateKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plaintext,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=list[KeyInfo])
async def list_api_keys(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current org (masked)."""
    org_id = user_data.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization found")

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.org_id == org_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        KeyInfo(
            id=k.id,
            name=k.name,
            key_preview=f"kron_...{k.key_hash[-4:]}",
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    org_id = user_data.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization found")

    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()
    return {"ok": True, "message": f"API key '{api_key.name}' revoked"}
