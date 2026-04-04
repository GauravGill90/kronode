"""Kronode configuration — reads from ~/.kronode/config.toml then env vars."""
import os
import tomllib
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

KRONODE_DIR = Path.home() / ".kronode"
CONFIG_FILE = KRONODE_DIR / "config.toml"
DEFAULT_DB = f"sqlite+aiosqlite:///{KRONODE_DIR / 'kronode.db'}"


def _load_toml() -> dict:
    """Load config from ~/.kronode/config.toml if it exists."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Mode
    mode: str = "local"  # "local" or "byok"

    # Database
    database_url: str = DEFAULT_DB

    # Repo (from config.toml [repo] section)
    repo_path: str = ""  # local path to git clone
    repo_provider: str = "github"  # github | gitlab | bitbucket
    repo_token: str = ""  # optional PAT for --with-prs

    # LLM key (BYOK mode) — single key, auto-detects provider
    llm_api_key: str = ""  # set LLM_API_KEY env var or llm_api_key in config.toml

    # Provider-specific keys (alternative to single LLM_API_KEY)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""

    # Org ID (always 1 for open-source single-tenant)
    org_id: int = 1

    def __init__(self, **kwargs):
        # Load from TOML first, then env vars override
        toml = _load_toml()
        repo = toml.get("repo", {})
        db = toml.get("database", {})
        byok = toml.get("byok", {})

        defaults = {
            "mode": toml.get("mode", "local"),
            "repo_path": repo.get("path", ""),
            "repo_provider": repo.get("provider", "github"),
            "repo_token": repo.get("token", ""),
            "database_url": db.get("url", DEFAULT_DB),
            "llm_api_key": byok.get("llm_api_key", ""),
        }

        # Env vars override toml
        for key, default in defaults.items():
            env_val = os.environ.get(key.upper(), "")
            if not env_val:
                kwargs.setdefault(key, default)

        # Auto-detect provider from single LLM_API_KEY
        llm_key = os.environ.get("LLM_API_KEY", "") or kwargs.get("llm_api_key", "") or defaults.get("llm_api_key", "")
        if llm_key:
            if llm_key.startswith("sk-ant-"):
                kwargs.setdefault("anthropic_api_key", llm_key)
            elif llm_key.startswith("sk-"):
                kwargs.setdefault("openai_api_key", llm_key)
            elif llm_key.startswith("AI"):
                kwargs.setdefault("gemini_api_key", llm_key)
            else:
                # Default to OpenAI-compatible
                kwargs.setdefault("openai_api_key", llm_key)

        # Also check provider-specific env vars directly
        for key in ("openai_api_key", "anthropic_api_key", "gemini_api_key", "deepseek_api_key"):
            env_val = os.environ.get(key.upper(), "")
            if env_val:
                kwargs[key] = env_val

        # Auto-detect mode
        has_llm = any(kwargs.get(k) for k in ("openai_api_key", "anthropic_api_key", "gemini_api_key", "deepseek_api_key", "llm_api_key"))
        if not kwargs.get("mode") or kwargs.get("mode") == "local":
            kwargs["mode"] = "byok" if has_llm else "local"

        super().__init__(**kwargs)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Backward compat alias
settings = get_settings()
