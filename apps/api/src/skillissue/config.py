"""Application configuration (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"
    database_url: str
    redis_url: str
    github_token: str = ""
    anthropic_api_key: str = ""
    llm_mode: str = "fake"
    triage_model_id: str
    fix_model_id: str
    pipeline_version: str = "0.1.0"
    scanner_image: str = "skillissue/scanner:0.1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
