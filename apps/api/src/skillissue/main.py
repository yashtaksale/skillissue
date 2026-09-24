"""FastAPI application factory."""
from fastapi import FastAPI

from skillissue.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SkillIssue API",
        version="0.1.0",
        docs_url="/docs" if settings.env != "prod" else None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
