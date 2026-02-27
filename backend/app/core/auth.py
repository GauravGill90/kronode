from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from clerk_backend_api.security import verify_token_async, VerifyTokenOptions

from app.core.config import settings

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
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
