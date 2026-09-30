"""FastAPI routes: create/list/get/stream scans, report endpoint.

Thin routing layer — all business logic lives in scan_service.py and scan_repo.py.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rq import Queue
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from skillissue.api.auth.routes import get_user_id
from skillissue.api.redis_events import subscribe_scan_events
from skillissue.db.models.tables import ScanStatusEnum
from skillissue.db.repositories.scan_repo import (
    create_scan,
    get_or_create_repo,
    get_scan_by_id,
    get_scans_for_repo,
)
from skillissue.db.session.async_session import get_session
from skillissue.config import get_settings
from skillissue.domain.url.exceptions import (
    ControlCharacterError,
    InvalidFormatError,
    TooLongError,
    URLError,
    UnsafeRepoError,
    UnsupportedHostError,
)
from skillissue.domain.url.models import RepoRef
from skillissue.domain.url.parser import parse
from skillissue.pipeline.denylist import check_denylist
from skillissue.pipeline.score import ScoredSignal
from skillissue.pipeline.scoring_engine import (
    compute_overall,
    summary_sentence,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["scans"])


# ── Rate limiting ────────────────────────────────────────────────────────

_rate_counts: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(client_ip: str) -> None:
    """Enforce hourly rate limit per IP."""
    settings = get_settings()
    now = time.time()
    cutoff = now - 3600
    _rate_counts[client_ip] = [
        ts for ts in _rate_counts[client_ip] if ts > cutoff
    ]
    if len(_rate_counts[client_ip]) >= settings.anon_rate_limit_hourly:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {settings.anon_rate_limit_hourly} scans per hour",
        )
    _rate_counts[client_ip].append(now)


# Maximum SSE stream duration (seconds)
_MAX_STREAM_SECONDS = 660


class ScanRequest(BaseModel):
    repo: str = Field(..., min_length=3, max_length=200, pattern=r"^[a-zA-Z0-9_./:@-]+$")


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/scans")
async def list_scans(
    user_id: str | None = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List recent scans. For now, since user_id is mostly demo, we return all (placeholder)."""
    # In a real app we'd fetch the user's repos. Returning empty for now or 
    # we could just query the scans table directly if we wanted.
    return {"scans": []}


@router.post("/scans")
async def create_scan_endpoint(
    body: ScanRequest,
    request: Request,
    user_id: str | None = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Start a new scan."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    repo_input = body.repo.strip()
    if not repo_input:
        raise HTTPException(status_code=400, detail="Missing 'repo' field")

    try:
        repo_ref = parse(repo_input)
    except URLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        check_denylist(repo_ref)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    repo = await get_or_create_repo(session, repo_ref.owner, repo_ref.repo)
    scan = await create_scan(
        session,
        repo_id=repo.id,
        commit_sha="",
        branch=repo_ref.ref,
        pipeline_version=get_settings().pipeline_version,
        ip_hash=client_ip,
    )
    
    # Enqueue to RQ
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    q = Queue("scans", connection=redis_conn)
    q.enqueue("skillissue.worker.tasks.run_scan_job", scan.id, body.repo)

    return {"id": scan.id, "repo": repo_ref.full_name, "status": scan.status.value}


@router.get("/scans/{scan_id}")
async def get_scan_endpoint(
    scan_id: str,
    user_id: str | None = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scan = await get_scan_by_id(session, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return {
        "id": scan.id,
        "repo": f"{scan.repo.owner}/{scan.repo.name}",
        "status": scan.status.value,
        "progress": scan.progress_pct,
        "score": scan.score,
        "tier": scan.tier,
        "files": scan.stats.get("files_scanned", 0),
        "loc": scan.stats.get("loc_total", 0),
        "languages": scan.stats.get("languages", []),
        "coverage": scan.coverage.value if scan.coverage else "full",
        "hygiene_flags": scan.stats.get("hygiene_flags", []),
        "error": scan.error_detail,
        "created_at": scan.created_at.timestamp(),
    }


@router.get("/scans/{scan_id}/report")
async def get_report_endpoint(
    scan_id: str,
    user_id: str | None = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scan = await get_scan_by_id(session, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != ScanStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Scan is {scan.status.value}, not complete",
        )

    # Convert findings back to dicts for UI
    findings_out = []
    for f in scan.findings:
        findings_out.append({
            "id": f.id,
            "rule_id": f.rule_id,
            "category": f.category.value,
            "severity": f.severity.value,
            "confidence": f.confidence,
            "message": f.title,
            "explanation": f.explanation,
            "file": f.file_path,
            "line": f.line_start,
            "line_end": f.line_end,
            "snippet": f.snippet,
        })

    return {
        "id": scan.id,
        "repo": f"{scan.repo.owner}/{scan.repo.name}",
        "ref": scan.branch,
        "commit_sha": scan.commit_sha,
        "overall_score": scan.score,
        "tier": scan.tier,
        "tier_color": "#FFFFFF", # In a real implementation, would map from tier
        "tier_glyph": "🔥",
        "summary": summary_sentence(scan.score or 0, len(scan.findings)),
        "coverage": scan.coverage.value if scan.coverage else "full",
        "files_scanned": scan.stats.get("files_scanned", 0),
        "loc_total": scan.stats.get("loc_total", 0),
        "languages": scan.stats.get("languages", []),
        "hygiene_flags": scan.stats.get("hygiene_flags", []),
        "findings": findings_out,
        "findings_count": len(scan.findings),
        "category_scores": scan.subscores or {},
        "pipeline_version": scan.pipeline_version,
    }


@router.get("/scans/{scan_id}/stream")
async def stream_scan_endpoint(
    scan_id: str,
    user_id: str | None = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE stream of scan progress events."""
    scan = await get_scan_by_id(session, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan.status == ScanStatusEnum.COMPLETED:
        async def completed_stream():
            yield f"data: {json.dumps({'status': 'complete', 'progress': 100, 'score': scan.score, 'tier': scan.tier, 'message': 'Scan complete'})}\n\n"
        return StreamingResponse(
            completed_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_stream():
        deadline = time.monotonic() + _MAX_STREAM_SECONDS
        async for event in subscribe_scan_events(scan_id):
            if time.monotonic() > deadline:
                yield f"data: {json.dumps({'status': 'failed', 'error': 'Stream timed out'})}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
