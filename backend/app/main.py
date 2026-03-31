import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (migrations handle production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Kronode API",
    version="0.2.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

# ── Rate Limiting ────────────────────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],
        storage_uri=settings.redis_url,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled (100/min default)")
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")

# ── Sentry ───────────────────────────────────────────────────────────────────
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
        )
        logger.info("Sentry error tracking enabled")
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking disabled")

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/v1")


# ── Integration webhooks ──────────────────────────────────────────────────────

@app.post("/integrations/github/webhooks")
async def github_webhook(request: Request):
    """Receive GitHub App webhook events."""
    from app.integrations.github_app import (
        handle_pull_request,
        handle_pull_request_review,
        verify_webhook_signature,
    )

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")

    if settings.github_webhook_secret:
        if not verify_webhook_signature(body, signature, settings.github_webhook_secret):
            return JSONResponse(status_code=401, content={"error": "Invalid signature"})

    import json
    payload = json.loads(body)

    if event == "pull_request":
        await handle_pull_request(payload)
    elif event == "pull_request_review":
        await handle_pull_request_review(payload)

    return {"ok": True}


@app.post("/integrations/slack/events")
async def slack_events(request: Request):
    """Receive Slack events (app_mention, slash commands)."""
    try:
        from app.integrations.slack_bot import handler
        return await handler.handle(request)
    except ImportError:
        return JSONResponse(status_code=501, content={"error": "slack-bolt not installed"})


@app.get("/health")
async def health():
    """Shallow health check — process is up."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Deep health check — verify Postgres + Redis connections."""
    checks = {}

    # Postgres
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)[:100]}"

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }
