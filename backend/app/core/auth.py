from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.org import Organization
from app.models.user import User


async def get_current_org_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> int:
    """
    Extract the Clerk organisation ID from the request headers and resolve
    the internal org primary key.

    Expects the API gateway / BFF to forward:
      X-Clerk-Org-Id: <clerk_org_id>

    In development, falls back to the first org in the database for convenience.
    """
    clerk_org_id: Optional[str] = request.headers.get("X-Clerk-Org-Id")

    if clerk_org_id:
        result = await db.execute(
            select(Organization).where(Organization.clerk_org_id == clerk_org_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation '{clerk_org_id}' not found.",
            )
        return org.id

    # Dev fallback — use the first org
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No organisation found. Complete Clerk setup first.",
        )
    return org.id
