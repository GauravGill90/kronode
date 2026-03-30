from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=not settings.bypass_auth)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    as_user: str | None = Query(None, alias="as_user", description="Dev only: override user ID"),
) -> dict:
    # Dev bypass — skip Clerk, optionally pick user via ?as_user=clerk_id
    if settings.bypass_auth:
        user_id = as_user or settings.bypass_auth_user_id
        return {"user_id": user_id, "session_id": "dev"}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    token = credentials.credentials
    try:
        from clerk_backend_api.security import verify_token_async, VerifyTokenOptions
        payload = await verify_token_async(
            token,
            VerifyTokenOptions(secret_key=settings.clerk_secret_key),
        )
        return {"user_id": payload["sub"], "session_id": payload.get("sid", "")}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
