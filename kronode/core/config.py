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

    # LLM keys (BYOK mode) — set any for richer extraction
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""

    # Ingestion settings
    kronode_pr_count: int = 200
    kronode_min_confidence: float = 0.5
    kronode_max_conventions: int = 20

    # MCP server
    kronode_transport: str = "stdio"
    kronode_port: int = 8001

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
            "openai_api_key": byok.get("openai_api_key", ""),
            "anthropic_api_key": byok.get("anthropic_api_key", ""),
            "gemini_api_key": byok.get("gemini_api_key", ""),
            "deepseek_api_key": byok.get("deepseek_api_key", ""),
        }

        # Env vars override toml
        for key, default in defaults.items():
            env_val = os.environ.get(key.upper(), "")
            if env_val:
                kwargs[key] = env_val
            else:
                kwargs.setdefault(key, default)

        # Auto-detect mode
        has_llm = any(kwargs.get(k) for k in ("openai_api_key", "anthropic_api_key", "gemini_api_key", "deepseek_api_key"))
        if not kwargs.get("mode") or kwargs.get("mode") == "local":
            kwargs["mode"] = "byok" if has_llm else "local"

        super().__init__(**kwargs)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Backward compat alias
settings = get_settings()
