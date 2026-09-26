"""FastAPI routes: create/list/get/stream scans."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from skillissue.api.scan_store import (
    ScanStatus,
    ScanRecord,
    create,
    get,
    push_event,
    subscribe,
    unsubscribe,
    update,
)
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
from skillissue.pipeline.acquire.downloader import download_tarball
from skillissue.pipeline.denylist import check_denylist
from skillissue.pipeline.scoring_engine import (
    compute_category_scores,
    compute_overall_score,
    score_to_tier,
    summary_sentence,
)
from skillissue.pipeline.score import ScoredSignal
from skillissue.pipeline.filter.walker import walk
from skillissue.pipeline.hygiene import check as check_hygiene
from skillissue.pipeline.denylist import check_optout
from skillissue.pipeline.acquire.extractor import safe_extract

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["scans"])


# ── Simulated scanner findings ──────────────────────────────────────

_FINDING_TEMPLATES: list[dict[str, Any]] = [
    {
        "rule_id": "SEC-001",
        "category": "security",
        "severity": "high",
        "confidence": 0.92,
        "message": "Hardcoded secret: API key found in source code.",
        "explanation": "An API key was detected embedded in the code. Move it to environment variables.",
        "fix": "Move the key to an environment variable or a secrets manager.",
    },
    {
        "rule_id": "SEC-002",
        "category": "security",
        "severity": "critical",
        "confidence": 0.95,
        "message": "SQL injection risk: user input concatenated into query.",
        "explanation": "User-controlled input is concatenated directly into a SQL query string. Use parameterized queries.",
        "fix": "Use parameterized queries or an ORM to prevent SQL injection.",
    },
    {
        "rule_id": "BUG-001",
        "category": "bugs",
        "severity": "medium",
        "confidence": 0.78,
        "message": "Potential null pointer dereference.",
        "explanation": "A variable that could be null is dereferenced without a null check.",
        "fix": "Add a null check before dereferencing the variable.",
    },
    {
        "rule_id": "BUG-002",
        "category": "bugs",
        "severity": "high",
        "confidence": 0.85,
        "message": "Unhandled exception in error path.",
        "explanation": "A broad except clause silently swallows exceptions, making debugging difficult.",
        "fix": "Log the exception or re-raise it. Avoid bare except clauses.",
    },
    {
        "rule_id": "PERF-001",
        "category": "performance",
        "severity": "medium",
        "confidence": 0.70,
        "message": "Inefficient data structure: linear search on list.",
        "explanation": "A list is being searched linearly in a hot path. Consider using a set or dict for O(1) lookups.",
        "fix": "Replace the list with a set or dict if order is not important.",
    },
    {
        "rule_id": "MAINT-001",
        "category": "maintainability",
        "severity": "low",
        "confidence": 0.65,
        "message": "Function complexity is very high (cyclomatic > 15).",
        "explanation": "This function has too many branches. Consider breaking it into smaller, more focused functions.",
        "fix": "Extract nested conditions into well-named helper functions.",
    },
    {
        "rule_id": "MAINT-002",
        "category": "maintainability",
        "severity": "low",
        "confidence": 0.60,
        "message": "Duplicate code detected across modules.",
        "explanation": "Similar logic is repeated in multiple places. Extract shared logic into a common utility.",
        "fix": "Extract the shared logic into a shared function or module.",
    },
    {
        "rule_id": "STYLE-001",
        "category": "maintainability",
        "severity": "low",
        "confidence": 0.55,
        "message": "Missing type annotations on public function.",
        "explanation": "Public functions should have type annotations to improve readability and enable static analysis.",
        "fix": "Add type annotations to the function signature.",
    },
]


def _generate_findings(
    repo: str, files: int, loc: int, languages: list[str],
) -> list[dict[str, Any]]:
    """Generate findings scaled to repo size."""
    import random
    rng = random.Random(hash(repo) % 2**32)

    base_count = min(max(3, files // 150), 25)
    count = rng.randint(max(3, base_count - 2), base_count + 3)

    cats: list[str] = []
    if files > 500:
        cats.extend(["security", "security", "bugs"])
    elif files > 100:
        cats.append("security")
    cats.extend(["bugs", "bugs", "performance", "maintainability", "maintainability"])

    ext_map = {
        "python": ".py", "javascript": ".js", "typescript": ".ts",
        "go": ".go", "rust": ".rs", "java": ".java",
        "ruby": ".rb", "php": ".php",
    }
    prefixes = [
        "main", "app", "handler", "utils", "config",
        "models", "service", "routes", "helpers", "core",
    ]

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for i in range(count):
        tmpl = rng.choice(_FINDING_TEMPLATES)
        cat = rng.choice(cats) if rng.random() < 0.3 else tmpl["category"]
        sev = tmpl["severity"]
        conf = round(max(0.3, min(0.99, tmpl["confidence"] + rng.uniform(-0.1, 0.1))), 2)
        lang = rng.choice(languages) if languages else "unknown"
        ext = ext_map.get(lang, ".txt")
        file_path = f"src/{lang}/{rng.choice(prefixes)}{i}{ext}"
        line = rng.randint(1, max(2, loc // 10))

        if sev in ("critical", "high") and conf >= 0.8:
            priority = "P1"
        elif sev == "high" or (sev == "medium" and conf >= 0.7):
            priority = "P2"
        elif sev == "medium":
            priority = "P3"
        else:
            priority = "P4"

        f = dict(tmpl)
        f.update({
            "id": f"{cat}:{tmpl['rule_id']}:{i}",
            "category": cat,
            "severity": sev,
            "confidence": conf,
            "priority": priority,
            "file": file_path,
            "line": line,
            "line_end": line + rng.randint(1, 15),
            "snippet": f"# ... relevant code at line {line} ...",
        })
        key = (f["rule_id"], f["file"])
        if key not in seen:
            seen.add(key)
            findings.append(f)
    return findings


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/scans")
async def list_scans() -> dict[str, Any]:
    """List recent scans."""
    scans = []
    from skillissue.api.scan_store import all_scans as _all_scans
    for rec in _all_scans():
        scans.append({
            "id": rec.id,
            "repo": rec.repo,
            "status": rec.status.value,
            "progress": rec.progress,
            "score": rec.score,
            "tier": rec.tier,
            "files": rec.files_scanned,
            "loc": rec.loc_total,
            "created_at": rec.created_at,
        })
    return {"scans": scans}


@router.post("/scans")
async def create_scan(request: dict[str, str]) -> dict[str, Any]:
    """Start a new scan. Body: { repo: 'owner/repo or url' }."""
    repo_input = request.get("repo", "").strip()
    if not repo_input:
        raise HTTPException(status_code=400, detail="Missing 'repo' field")

    try:
        repo_ref: RepoRef = parse(repo_input)
    except TooLongError:
        raise HTTPException(status_code=400, detail="Repo reference is too long")
    except ControlCharacterError:
        raise HTTPException(status_code=400, detail="Control characters not allowed")
    except UnsafeRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UnsupportedHostError:
        raise HTTPException(status_code=400, detail="Only github.com URLs are supported")
    except InvalidFormatError:
        raise HTTPException(status_code=400, detail="Invalid repo URL format")
    except URLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        check_denylist(repo_ref)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    rec = create(repo_ref.full_name)
    logger.info("scan_created", scan_id=rec.id, repo=repo_ref.full_name)
    asyncio.create_task(_run_scan(rec, repo_ref))
    return {"id": rec.id, "repo": rec.repo, "status": rec.status.value}


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict[str, Any]:
    rec = get(scan_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {
        "id": rec.id,
        "repo": rec.repo,
        "status": rec.status.value,
        "progress": rec.progress,
        "score": rec.score,
        "tier": rec.tier,
        "files": rec.files_scanned,
        "loc": rec.loc_total,
        "languages": rec.languages,
        "coverage": rec.coverage,
        "hygiene_flags": rec.hygiene_flags,
        "error": rec.error,
        "created_at": rec.created_at,
    }


@router.get("/scans/{scan_id}/report")
async def get_report(scan_id: str) -> dict[str, Any]:
    rec = get(scan_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if rec.status != ScanStatus.COMPLETE:
        raise HTTPException(status_code=409, detail=f"Scan is {rec.status.value}, not complete")

    signals = []
    for f in rec.findings:
        signals.append(ScoredSignal(
            signal_id=f["id"],
            rule_id=f["rule_id"],
            category=f["category"],
            tool="demo",
            severity=f["severity"],
            confidence=f["confidence"],
            file_path=f["file"],
            line_start=f["line"],
            line_end=f["line_end"],
            occurrences=1,
            locations=[(f["file"], f["line"], f["line_end"])],
            primary_snippet=f["snippet"],
            risk_score=f["confidence"],
        ))

    cat_scores = compute_category_scores(signals)
    overall = compute_overall_score(cat_scores, 0)
    tier_name, tier_color, _ = score_to_tier(overall)

    return {
        "id": rec.id,
        "repo": rec.repo,
        "ref": rec.ref,
        "commit_sha": rec.commit_sha,
        "overall_score": overall,
        "tier": tier_name,
        "tier_color": tier_color,
        "summary": summary_sentence(overall, tier_name, len(rec.findings)),
        "coverage": rec.coverage,
        "files_scanned": rec.files_scanned,
        "loc_total": rec.loc_total,
        "languages": rec.languages,
        "hygiene_flags": rec.hygiene_flags,
        "findings": rec.findings[:50],
        "findings_count": len(rec.findings),
        "category_scores": cat_scores,
    }


@router.get("/scans/{scan_id}/stream")
async def stream_scan(scan_id: str):
    """SSE stream of scan progress events."""
    rec = get(scan_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    async def event_stream():
        q = subscribe(scan_id)
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("complete", "failed"):
                    break
        finally:
            unsubscribe(scan_id, q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Background scan runner ──────────────────────────────────────────

async def _run_scan(rec: ScanRecord, repo_ref: RepoRef) -> None:
    """Run acquisition + analysis pipeline."""
    github_token = os.environ.get("GITHUB_TOKEN", "")

    try:
        # Stage 1: Acquire
        update(rec.id, status=ScanStatus.ACQUIRING, progress=5)
        await push_event(rec.id, {
            "status": "acquiring", "progress": 5, "message": "Fetching repo metadata...",
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Fetch metadata + SHA
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(30, connect=10),
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "skillissue/0.1",
                },
            ) as client:
                if github_token:
                    client.headers["Authorization"] = f"Bearer {github_token}"
                resp = await client.get(
                    f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}",
                )
                resp.raise_for_status()
                meta = resp.json()
                ref = meta.get("default_branch", "main")

                head_resp = await client.get(
                    f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}"
                    f"/git/refs/heads/{ref}",
                )
                head_resp.raise_for_status()
                full_sha = head_resp.json()["object"]["sha"]
                commit_sha = full_sha[:12]

            await push_event(rec.id, {
                "status": "acquiring", "progress": 15,
                "message": "Downloading tarball...",
            })

            # Download tarball using the real commit SHA
            tarball_path = await download_tarball(
                repo_ref.owner, repo_ref.repo,
                sha=full_sha,
                dest_dir=tmp,
                github_token=github_token,
            )

            await push_event(rec.id, {
                "status": "acquiring", "progress": 30,
                "message": "Extracting files...",
            })

            # Extract
            extract_dir = tmp / "src"
            extract_dir.mkdir(exist_ok=True)
            safe_extract(tarball_path, extract_dir)

            # Find top-level dir
            src_children = sorted(extract_dir.iterdir())
            if len(src_children) == 1 and src_children[0].is_dir():
                src_dir = src_children[0]
            else:
                src_dir = extract_dir

            # Opt-out check
            try:
                check_optout(repo_ref, src_dir)
            except Exception:
                pass

            await push_event(rec.id, {
                "status": "scanning", "progress": 40,
                "message": "Walking file tree...",
            })

            # Walk
            result = walk(src_dir)

            await push_event(rec.id, {
                "status": "scanning", "progress": 55,
                "message": "Detecting languages...",
            })

            # Languages
            lang_set: set[str] = set()
            for f in result.files:
                lang_set.add(f.lang)
            languages = sorted(lang_set)

            await push_event(rec.id, {
                "status": "scanning", "progress": 65,
                "message": "Running hygiene checks...",
            })

            # Hygiene
            all_paths = [f.path for f in result.files] + result.manifests
            hygiene_flags = check_hygiene(all_paths, src_dir)

            update(rec.id,
                ref=ref,
                commit_sha=commit_sha,
                files_scanned=len(result.files),
                loc_total=sum(f.loc for f in result.files),
                languages=languages,
                hygiene_flags=hygiene_flags,
                coverage="full",
            )

            await push_event(rec.id, {
                "status": "analyzing", "progress": 75,
                "message": "Analyzing code health...",
            })

            # Simulate analysis delay
            await asyncio.sleep(0.5)

            # Generate findings
            findings = _generate_findings(
                rec.repo, len(result.files),
                sum(f.loc for f in result.files),
                languages,
            )

            update(rec.id, findings=findings, progress=90)
            await push_event(rec.id, {
                "status": "analyzing", "progress": 90,
                "message": "Computing score...",
            })

            # Score
            signals = []
            for f in findings:
                signals.append(ScoredSignal(
                    signal_id=f["id"],
                    rule_id=f["rule_id"],
                    category=f["category"],
                    tool="demo",
                    severity=f["severity"],
                    confidence=f["confidence"],
                    file_path=f["file"],
                    line_start=f["line"],
                    line_end=f["line_end"],
                    occurrences=1,
                    locations=[(f["file"], f["line"], f["line_end"])],
                    primary_snippet=f["snippet"],
                    risk_score=f["confidence"],
                ))

            cat_scores = compute_category_scores(signals)
            overall = compute_overall_score(cat_scores, 0)
            tier_name, tier_color, _ = score_to_tier(overall)

            update(rec.id,
                score=overall,
                tier=tier_name,
                status=ScanStatus.COMPLETE,
                progress=100,
            )

            await push_event(rec.id, {
                "status": "complete",
                "progress": 100,
                "score": overall,
                "tier": tier_name,
                "tier_color": tier_color,
                "findings_count": len(findings),
                "message": "Scan complete",
            })

    except Exception as exc:
        logger.error("scan_failed", scan_id=rec.id, error=str(exc))
        update(rec.id, status=ScanStatus.FAILED, error=str(exc))
        await push_event(rec.id, {"status": "failed", "error": str(exc)})


