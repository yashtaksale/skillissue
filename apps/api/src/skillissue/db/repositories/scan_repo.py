"""Scan repository — DB CRUD for scans and findings.

When the full Postgres persistence is wired up (T-6.2), routes and services
will call these instead of scan_store.py. For now, scan_store.py remains
the in-memory implementation used at runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update as sql_update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from skillissue.db.models.tables import (
    Finding,
    FindingCategory,
    FindingSeverity,
    Repo,
    Scan,
    ScanEvent,
    ScanStatusEnum,
    CoverageKind,
)


async def get_or_create_repo(
    session: AsyncSession,
    owner: str,
    name: str,
    *,
    host: str = "github.com",
    github_meta: dict[str, Any] | None = None,
) -> Repo:
    """Upsert a repo row by (host, owner, name)."""
    stmt = select(Repo).where(
        Repo.host == host,
        Repo.owner == owner.lower(),
        Repo.name == name.lower(),
    )
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if repo is not None:
        # Update metadata if provided
        if github_meta:
            repo.github_id = github_meta.get("id")
            repo.default_branch = github_meta.get("default_branch")
            repo.is_fork = github_meta.get("fork", False)
            repo.is_archived = github_meta.get("archived", False)
            repo.stars = github_meta.get("stargazers_count")
            repo.primary_language = github_meta.get("language")
            repo.updated_at = datetime.now(timezone.utc)
            await session.commit()
        return repo

    repo = Repo(
        id=str(uuid4()),
        host=host,
        owner=owner,
        name=name,
        github_id=github_meta.get("id") if github_meta else None,
        default_branch=github_meta.get("default_branch") if github_meta else None,
        is_fork=github_meta.get("fork", False) if github_meta else False,
        is_archived=github_meta.get("archived", False) if github_meta else False,
        stars=github_meta.get("stargazers_count") if github_meta else None,
        primary_language=github_meta.get("language") if github_meta else None,
    )
    session.add(repo)
    await session.commit()
    return repo


async def create_scan(
    session: AsyncSession,
    repo_id: str,
    commit_sha: str,
    branch: str,
    pipeline_version: str,
    *,
    ip_hash: str = "",
    options_hash: str = "",
) -> Scan:
    """Insert a new scan row."""
    scan = Scan(
        id=str(uuid4()),
        repo_id=repo_id,
        commit_sha=commit_sha,
        branch=branch,
        pipeline_version=pipeline_version,
        options_hash=options_hash,
        ip_hash=ip_hash,
    )
    session.add(scan)
    await session.commit()
    return scan


async def update_scan_status(
    session: AsyncSession,
    scan_id: str,
    status: ScanStatusEnum,
    *,
    progress_pct: int | None = None,
    score: int | None = None,
    tier: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    coverage: CoverageKind | None = None,
    stats: dict | None = None,
    subscores: dict | None = None,
) -> None:
    """Update scan status and optional fields."""
    values: dict[str, Any] = {"status": status}
    if progress_pct is not None:
        values["progress_pct"] = progress_pct
    if score is not None:
        values["score"] = score
    if tier is not None:
        values["tier"] = tier
    if error_code is not None:
        values["error_code"] = error_code
    if error_detail is not None:
        values["error_detail"] = error_detail
    if coverage is not None:
        values["coverage"] = coverage
    if stats is not None:
        values["stats"] = stats
    if subscores is not None:
        values["subscores"] = subscores

    if status == ScanStatusEnum.COMPLETED:
        values["finished_at"] = datetime.now(timezone.utc)
    elif status in (ScanStatusEnum.CLONING, ScanStatusEnum.SCANNING):
        values["started_at"] = datetime.now(timezone.utc)

    stmt = sql_update(Scan).where(Scan.id == scan_id).values(**values)
    await session.execute(stmt)
    await session.commit()


async def insert_findings(
    session: AsyncSession,
    scan_id: str,
    findings: list[dict[str, Any]],
) -> list[Finding]:
    """Bulk-insert findings for a scan."""
    rows = []
    for f in findings:
        row = Finding(
            id=str(uuid4()),
            scan_id=scan_id,
            category=FindingCategory(f.get("category", "maintainability")),
            severity=FindingSeverity(f.get("severity", "medium")),
            confidence=f.get("confidence", 0.5),
            title=f.get("message", "")[:80],
            explanation=f.get("explanation", ""),
            file_path=f.get("file", ""),
            line_start=f.get("line", 1),
            line_end=f.get("line_end", 1),
            snippet=f.get("snippet", ""),
            fingerprint=f.get("fingerprint", ""),
            rule_id=f.get("rule_id", ""),
            tool=f.get("tool", "scanner"),
            visible=True,
        )
        session.add(row)
        rows.append(row)
    await session.commit()
    return rows


async def insert_scan_event(
    session: AsyncSession,
    scan_id: str,
    kind: str,
    payload: dict[str, Any],
) -> ScanEvent:
    """Insert a scan progress event."""
    event = ScanEvent(
        scan_id=scan_id,
        kind=kind,
        payload=payload,
    )
    session.add(event)
    await session.commit()
    return event


async def get_scan_by_id(
    session: AsyncSession,
    scan_id: str,
) -> Scan | None:
    """Fetch a scan by ID with findings."""
    try:
        from uuid import UUID
        UUID(scan_id)
    except (ValueError, AttributeError):
        return None
    stmt = (
        select(Scan)
        .options(selectinload(Scan.repo), selectinload(Scan.findings))
        .where(Scan.id == scan_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_scans_for_repo(
    session: AsyncSession,
    repo_id: str,
    *,
    limit: int = 20,
) -> list[Scan]:
    """List recent scans for a repo."""
    stmt = (
        select(Scan)
        .where(Scan.repo_id == repo_id)
        .order_by(Scan.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
