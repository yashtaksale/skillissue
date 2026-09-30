from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql+asyncpg://skillissue:skillissue@localhost:5432/skillissue"
    redis_url: str = "redis://localhost:6379/0"
    github_token: str = ""
    anthropic_api_key: str = ""
    llm_mode: str = "fake"
    llm_triage_model: str = "claude-sonnet-4"
    llm_fix_model: str = "claude-opus-4"
    pipeline_version: str = "0.1.0"
    scanner_image: str = "skillissue/scanner:0.1.0"

    # JWT
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Frontend URL (used for CORS)
    site_url: str = "http://localhost:3000"

    # Rate limiting
    anon_rate_limit_hourly: int = 100
    anon_rate_limit_daily: int = 1000
    per_repo_cooldown_seconds: int = 600
    queue_depth_cap: int = 50

    # Scan limits
    scan_wall_clock_seconds: int = 600
    max_concurrent_scans: int = 10

    model_config = SettingsConfigDict(
        env_file=(_BASE_DIR / ".env", ".env", "apps/api/.env"),
        extra="ignore"
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
