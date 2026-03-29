from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=not settings.bypass_auth)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    # Dev bypass — skip Clerk entirely
    if settings.bypass_auth:
        return {"user_id": settings.bypass_auth_user_id, "session_id": "dev"}

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
