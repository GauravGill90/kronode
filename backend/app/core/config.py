from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Clerk
    clerk_secret_key: str = ""
    next_public_clerk_publishable_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kronode"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str = ""

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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
