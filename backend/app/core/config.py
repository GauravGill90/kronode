from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file (backend/app/core/config.py → backend/.env)
# This ensures the worker finds the right .env regardless of where it's started from.
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Clerk
    clerk_secret_key: str = ""
    next_public_clerk_publishable_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kronode"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic (required — used for quality calls: planner, coder, reviewer)
    anthropic_api_key: str = ""

    # Cheap LLM providers — set API keys for any/all, auto-failover cheapest first
    # Order: Gemini (free) → DeepSeek ($0.27/MTok) → OpenAI ($0.15/MTok) → Haiku ($0.80/MTok)
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # Jira OAuth
    jira_client_id: str = ""
    jira_client_secret: str = ""

    # Slack OAuth
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""

    # App
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    # Dev / testing
    bypass_llm: bool = False  # set BYPASS_LLM=true to skip all LLM calls and test GitHub PR directly
    bypass_auth: bool = False  # set BYPASS_AUTH=true to skip Clerk JWT verification (dev only)
    bypass_auth_user_id: str = "dev_user"  # user_id used when auth is bypassed

    # Claude Agent SDK (coder agent execution engine)
    agent_sdk_model: str = "haiku"  # haiku | sonnet | opus
    agent_sdk_fallback_model: str = "sonnet"  # model to use on retry after failure
    agent_sdk_max_turns: int = 15  # max tool round-trips per task

    # Beat schedule — set to true to enable automatic polling
    enable_poll_pr: bool = True        # ENABLE_POLL_PR=true to auto-poll PR outcomes
    enable_poll_clarification: bool = True  # ENABLE_POLL_CLARIFICATION=true to auto-poll Slack threads
    enable_convention_refresh: bool = False  # ENABLE_CONVENTION_REFRESH=true to weekly refresh conventions

    # Pipeline step flags — set to true to skip individual agents
    skip_ticket_interpreter: bool = False
    skip_context_builder: bool = False
    skip_clarification: bool = False
    skip_planner: bool = False
    skip_plan_posting: bool = False
    skip_guardrails: bool = False
    skip_coder: bool = False
    skip_tester: bool = False
    skip_execution_verifier: bool = False
    skip_reviewer: bool = False
    skip_memory: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
