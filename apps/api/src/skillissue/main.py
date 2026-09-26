"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skillissue.config import get_settings
from skillissue.api.routes import router as scans_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SkillIssue API",
        version="0.1.0",
        docs_url="/docs" if settings.env != "prod" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(scans_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
