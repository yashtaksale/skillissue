# SkillIssue

How cooked is your code?

Paste a GitHub repo URL, get a score (0–100) and a ranked list of real problems grounded in deterministic static analysis.

## Local setup

```bash
# clone, then:
make dev          # start all services (docker compose)
make test         # run all tests
make lint         # ruff + eslint
make typecheck    # mypy + tsc
```

## Stack

- **Web:** Next.js 14 (App Router) + TypeScript + Tailwind
- **API:** FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic
- **Workers:** Redis + RQ
- **DB:** PostgreSQL 16
- **Sandbox:** Docker (rootless preferred, hardened flags)
- **Scanners:** Bandit, ESLint security rules, gitleaks, OSV-Scanner, Lizard, Radon
- **LLM:** Anthropic Claude (Haiku for analysis, Sonnet for fixes)

## Docs

- `PRD.md` — product requirements
- `ARCHITECTURE.md` — system design
- `DESIGN.md` — UI/UX and visual design
- `TASK.md` — task breakdown and schedule
- `RULES.md` — engineering rules
- `MEMORY.md` — decisions and running log
