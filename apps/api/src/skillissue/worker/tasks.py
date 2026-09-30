"""RQ worker tasks."""
from __future__ import annotations

import asyncio
from typing import Any

from skillissue.api.scan_service import run_scan_pipeline
from skillissue.db.repositories.scan_repo import get_scan_by_id
from skillissue.db.session.async_session import get_session_factory, dispose_engine
from skillissue.domain.url.parser import parse


def run_scan_job(scan_id: str, repo_url: str) -> None:
    """RQ task entrypoint. Runs the async pipeline synchronously for RQ."""
    asyncio.run(_async_run_scan_job(scan_id, repo_url))


async def _async_run_scan_job(scan_id: str, repo_url: str) -> None:
    """Async wrapper to load from DB and run the pipeline."""
    try:
        repo_ref = parse(repo_url)
        factory = get_session_factory()
        async with factory() as session:
            scan = await get_scan_by_id(session, scan_id)
            if not scan:
                return

        await run_scan_pipeline(scan_id, repo_ref)
    finally:
        await dispose_engine()
