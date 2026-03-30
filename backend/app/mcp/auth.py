"""API key authentication for the MCP server.

Org-scoped API keys — simpler than Clerk JWT, designed for machine-to-machine.
"""
import hashlib
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

KEY_PREFIX = "kron_"


def generate_key() -> tuple[str, str]:
    """Generate a new API key. Returns (plaintext_key, key_hash).

    The plaintext is shown to the user ONCE. We only store the hash.
    """
    raw = secrets.token_urlsafe(32)
    plaintext = f"{KEY_PREFIX}{raw}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, key_hash


def hash_key(plaintext: str) -> str:
    """Hash a plaintext API key for lookup."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


async def validate_token(token: str) -> "ApiKey":
    """Validate an API token and return the ApiKey record.

    Raises ValueError if invalid.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.api_key import ApiKey

    if not token.startswith(KEY_PREFIX):
        raise ValueError("Invalid token format — must start with kron_")

    token_hash = hash_key(token)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == token_hash)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise ValueError("Invalid API token")

        # Update last_used timestamp
        from datetime import datetime, timezone
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        return api_key
