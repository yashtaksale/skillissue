"""In-memory scan store for the demo (no Redis/DB needed)."""
from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any


class ScanStatus(str, Enum):
    QUEUED = "queued"
    ACQUIRING = "acquiring"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class ScanRecord:
    __slots__ = (
        "id", "repo", "ref", "status", "progress",
        "files_scanned", "loc_total", "languages",
        "coverage", "findings", "hygiene_flags",
        "score", "tier", "error", "created_at",
        "updated_at", "commit_sha",
    )

    def __init__(self, repo: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.repo = repo
        self.ref: str = ""
        self.commit_sha = ""
        self.status = ScanStatus.QUEUED
        self.progress = 0
        self.files_scanned = 0
        self.loc_total = 0
        self.languages: list[str] = []
        self.coverage = "full"
        self.findings: list[dict[str, Any]] = []
        self.hygiene_flags: list[str] = []
        self.score: int = 0
        self.tier: str = "Raw"
        self.error: str | None = None
        self.created_at = time.time()
        self.updated_at = time.time()


_store: dict[str, ScanRecord] = {}
_subscribers: dict[str, list[asyncio.Queue]] = {}


def create(repo: str) -> ScanRecord:
    rec = ScanRecord(repo)
    _store[rec.id] = rec
    return rec


def get(scan_id: str) -> ScanRecord | None:
    return _store.get(scan_id)


def all_scans() -> list[ScanRecord]:
    return sorted(_store.values(), key=lambda r: r.created_at, reverse=True)


def update(scan_id: str, **kwargs: Any) -> ScanRecord | None:
    rec = _store.get(scan_id)
    if rec is None:
        return None
    for k, v in kwargs.items():
        if hasattr(rec, k):
            setattr(rec, k, v)
    rec.updated_at = time.time()
    return rec


async def push_event(scan_id: str, event: dict) -> None:
    for q in _subscribers.get(scan_id, []):
        await q.put(event)


def subscribe(scan_id: str) -> asyncio.Queue:
    if scan_id not in _subscribers:
        _subscribers[scan_id] = []
    q: asyncio.Queue = asyncio.Queue()
    _subscribers[scan_id].append(q)
    return q


def unsubscribe(scan_id: str, q: asyncio.Queue) -> None:
    _subscribers.get(scan_id, []).clear()
