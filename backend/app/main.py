from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cors import configure_cors
from app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Kronode API",
    version="0.1.0",
    lifespan=lifespan,
    # Never expose the OpenAPI docs in production
    docs_url=None if __import__("os").getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if __import__("os").getenv("ENVIRONMENT") == "production" else "/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────────────
configure_cors(app)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(api_router)
