"""CORS configuration for the Kronode FastAPI application.

Only origins listed here will be accepted by the server.  Never use
allow_origins=["*"] in production — the frontend origin must be
explicitly declared.
"""

import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


def _get_allowed_origins() -> list[str]:
    """Build the list of allowed CORS origins from environment variables.

    ALLOWED_ORIGINS — comma-separated list of fully-qualified origins,
    e.g. ``https://app.kronode.io,http://localhost:3000``.
    Falls back to localhost for local development only when
    ENVIRONMENT != 'production'.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]

    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        # In production we refuse to fall back — fail loudly.
        raise RuntimeError(
            "ALLOWED_ORIGINS env var must be set in production. "
            "Never use wildcard CORS in production."
        )

    return ["http://localhost:3000"]


def configure_cors(app: FastAPI) -> None:
    """Attach the CORSMiddleware to *app* with safe, explicit settings."""
    allowed_origins = _get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
