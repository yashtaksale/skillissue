# ===== Stage 1: Build =====
FROM python:3.12-slim@sha256:7c3e3e7c3e3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7 AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install -r <(python -c "import tomllib; t=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(t.get('project',{}).get('dependencies',[])))") 2>/dev/null || pip install --no-cache-dir --prefix=/install fastapi pydantic sqlalchemy alembic asyncpg redis rq httpx structlog python-dotenv

# ===== Stage 2: Runtime =====
FROM python:3.12-slim@sha256:7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7c3e3e7 AS runtime

RUN groupadd -r skillissue && useradd -r -g skillissue -d /home/skillissue -s /sbin/nologin skillissue \
    && mkdir -p /home/skillissue /app \
    && chown -R skillissue:skillissue /home/skillissue /app

COPY --from=builder /install /usr/local

WORKDIR /app
COPY src/skillissue/src/ src/skillissue/src/  # populated at build time via docker-compose

USER skillissue
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "skillissue.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
