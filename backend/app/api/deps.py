"""FastAPI dependency injection helpers.

All protected endpoints must declare ``current_user: User = Depends(get_current_user)``
so that authentication is enforced consistently at the framework level rather
than ad-hoc per route handler.
"""

from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.user_service import get_or_create_user

_bearer = HTTPBearer(auto_error=True)
_CLERK_JWKS_URL_TEMPLATE = "https://api.clerk.com/v1/jwks"


async def _verify_clerk_token(token: str) -> dict:
    """Verify a Clerk JWT and return its claims.

    We delegate verification to Clerk's own token-verification endpoint so
    we never have to manage JWKS rotation ourselves.
    """
    secret_key = os.environ["CLERK_SECRET_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.clerk.com/v1/tokens/verify",
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            },
            json={"token": token},
            timeout=10,
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return resp.json()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and verify the bearer token then resolve the local User row."""
    claims = await _verify_clerk_token(credentials.credentials)
    clerk_id: str = claims.get("sub", "")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject claim is missing.",
        )
    user = await get_or_create_user(db, clerk_id=clerk_id)
    return user


# Convenience type alias for route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
