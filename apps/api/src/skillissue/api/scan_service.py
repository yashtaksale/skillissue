"""Scan pipeline service — orchestrates acquisition, analysis, and scoring.

This module owns the end-to-end scan lifecycle. Routes enqueue into RQ,
and RQ workers run this module.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
import structlog

from skillissue.api.redis_events import publish_scan_event
from skillissue.db.models.tables import ScanStatusEnum, CoverageKind
from skillissue.db.repositories.scan_repo import (
    update_scan_status,
    insert_findings,
    insert_scan_event,
)
from skillissue.db.session.async_session import get_session_factory
from skillissue.config import get_settings
from skillissue.domain.url.models import RepoRef
from skillissue.pipeline.acquire.downloader import DownloadError, download_tarball
from skillissue.pipeline.acquire.extractor import ExtractError, safe_extract
from skillissue.pipeline.denylist import RepoOptedOutError, check_optout
from skillissue.pipeline.filter.walker import walk
from skillissue.pipeline.hygiene import check as check_hygiene
from skillissue.pipeline.score import ScoredSignal
from skillissue.pipeline.scoring_engine import compute_overall
from skillissue.pipeline.llm.analyzer import analyze_chunks, merge_llm_findings
from skillissue.pipeline.sample.chunker import chunk_repo

logger = structlog.get_logger()


async def push_event(scan_id: str, event: dict) -> None:
    """Helper to publish event and store it safely without crashing the scan pipeline."""
    try:
        await publish_scan_event(scan_id, event)
    except Exception as exc:
        logger.warning("push_event_publish_failed", scan_id=scan_id, error=str(exc))

    try:
        factory = get_session_factory()
        async with factory() as session:
            await insert_scan_event(session, scan_id, event.get("status", "info"), event)
    except Exception as exc:
        logger.warning("push_event_insert_failed", scan_id=scan_id, error=str(exc))


async def run_scan_pipeline(scan_id: str, repo_ref: RepoRef) -> None:
    """Acquire → Walk → Hygiene → Analyze → Score → Complete.
    
    Now driven by RQ background worker with Postgres persistence.
    """
    github_token = os.environ.get("GITHUB_TOKEN", "")
    factory = get_session_factory()

    try:
        # ── Stage 1: Acquire ────────────────────────────────────────
        async with factory() as session:
            await update_scan_status(session, scan_id, ScanStatusEnum.CLONING, progress_pct=5)
            
        await push_event(scan_id, {
            "status": "acquiring", "progress": 5,
            "message": "Fetching repo metadata...",
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Resolve metadata + commit SHA
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(15, connect=5),
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
                if resp.status_code == 404:
                    raise ValueError(f"Repository '{repo_ref.full_name}' was not found on GitHub. Please verify the owner and name, or ensure it is a public repository.")
                elif resp.status_code == 403:
                    raise ValueError("GitHub API rate limit exceeded. Set GITHUB_TOKEN in your environment for 5,000 requests/hr.")
                resp.raise_for_status()
                meta = resp.json()
                ref = meta.get("default_branch", "main")

                head_resp = await client.get(
                    f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}/commits/{ref}",
                )
                head_resp.raise_for_status()
                full_sha = head_resp.json().get("sha", "")
                commit_sha = full_sha[:12] if full_sha else "HEAD"

            await push_event(scan_id, {
                "status": "acquiring", "progress": 15,
                "message": "Downloading tarball...",
            })

            tarball_path = await download_tarball(
                repo_ref.owner, repo_ref.repo,
                sha=full_sha, dest_dir=tmp,
                github_token=github_token,
            )

            await push_event(scan_id, {
                "status": "acquiring", "progress": 30,
                "message": "Extracting files...",
            })

            extract_dir = tmp / "src"
            extract_dir.mkdir(exist_ok=True)
            safe_extract(tarball_path, extract_dir)

            src_children = sorted(extract_dir.iterdir())
            if len(src_children) == 1 and src_children[0].is_dir():
                src_dir = src_children[0]
            else:
                src_dir = extract_dir

            # ── Opt-out check ───────────────────────────────────────
            try:
                check_optout(repo_ref, src_dir)
            except RepoOptedOutError:
                logger.info("scan_opted_out", scan_id=scan_id, repo=repo_ref.full_name)
                async with factory() as session:
                    await update_scan_status(
                        session, scan_id, ScanStatusEnum.FAILED,
                        error_detail="Repository has opted out of scanning"
                    )
                await push_event(scan_id, {
                    "status": "failed",
                    "error": "Repository has opted out of scanning",
                })
                return

            # ── Stage 2: Walk + detect ──────────────────────────────
            async with factory() as session:
                await update_scan_status(session, scan_id, ScanStatusEnum.SCANNING, progress_pct=40)
            await push_event(scan_id, {
                "status": "scanning", "progress": 40,
                "message": "Walking file tree...",
            })
            walk_result = walk(src_dir)

            lang_set: set[str] = set()
            for f in walk_result.files:
                if f.lang and f.lang != "unknown":
                    lang_set.add(f.lang)
            languages = sorted(lang_set)

            # ── Stage 3: Hygiene ────────────────────────────────────
            await push_event(scan_id, {
                "status": "scanning", "progress": 55,
                "message": "Running hygiene checks...",
            })
            all_paths = [f.path for f in walk_result.files] + walk_result.manifests
            hygiene_flags = check_hygiene(all_paths, src_dir)

            total_loc = sum(f.loc for f in walk_result.files)
            
            async with factory() as session:
                await update_scan_status(
                    session, scan_id, ScanStatusEnum.SCANNING,
                    stats={
                        "files_scanned": len(walk_result.files),
                        "loc_total": total_loc,
                        "languages": languages,
                        "hygiene_flags": hygiene_flags,
                    },
                    coverage=CoverageKind.FULL,
                )

            # ── Stage 4: Scanner analysis ───────────────────────────
            async with factory() as session:
                await update_scan_status(session, scan_id, ScanStatusEnum.ANALYZING, progress_pct=65)
            await push_event(scan_id, {
                "status": "analyzing", "progress": 65,
                "message": "Running static analysis...",
            })

            raw_signals = await _run_scanners(src_dir, walk_result.files)

            await push_event(scan_id, {
                "status": "analyzing", "progress": 80,
                "message": "Processing scanner findings...",
            })

            scanner_findings = _signals_to_findings(raw_signals, src_dir)
            scored_signals = _findings_to_scored(scanner_findings)

            # ── Stage 4.5: LLM Analysis ─────────────────────────────
            settings = get_settings()
            if settings.llm_mode != "fake":
                await push_event(scan_id, {
                    "status": "analyzing", "progress": 85,
                    "message": "Running AI analysis...",
                })
                
                # Chunk the files
                file_paths = [f.path for f in walk_result.files]
                chunks = chunk_repo(src_dir, file_paths)
                
                # Run LLM analysis
                llm_result = await analyze_chunks(
                    chunks=chunks,
                    signals=scored_signals,
                    api_key=settings.anthropic_api_key,
                )
                
                # Merge findings
                scored_signals = merge_llm_findings(scored_signals, llm_result.findings)

            # Convert merged findings back to dicts for DB
            final_findings = []
            for s in scored_signals:
                final_findings.append({
                    "id": s.signal_id,
                    "rule_id": s.rule_id,
                    "category": s.category,
                    "severity": s.severity,
                    "confidence": s.confidence,
                    "message": f"[{s.tool}:{s.rule_id}] Issue detected",
                    "explanation": f"Detected by {s.tool}",
                    "file": s.file_path,
                    "line": s.line_start,
                    "line_end": s.line_end,
                    "snippet": s.primary_snippet,
                    "fingerprint": f"{s.tool}:{s.rule_id}:{s.file_path}:{s.line_start}",
                    "tool": s.tool,
                })

            async with factory() as session:
                await insert_findings(session, scan_id, final_findings)
                await update_scan_status(session, scan_id, ScanStatusEnum.SCORING, progress_pct=90)

            await push_event(scan_id, {
                "status": "analyzing", "progress": 90,
                "message": "Computing score...",
            })

            # ── Stage 5: Score ──────────────────────────────────────
            score_result = compute_overall(
                findings=scored_signals,
                loc_analyzed=total_loc,
                hygiene_flags=hygiene_flags,
            )

            category_scores = {
                name: {
                    "value": cs.value,
                    "raw": cs.raw,
                    "density": cs.density,
                    "k_c": cs.k_c,
                }
                for name, cs in score_result.subscores.items()
            }

            async with factory() as session:
                await update_scan_status(
                    session, scan_id, ScanStatusEnum.COMPLETED,
                    progress_pct=100,
                    score=score_result.overall,
                    tier=score_result.tier.name,
                    subscores=category_scores,
                )

            await push_event(scan_id, {
                "status": "complete",
                "progress": 100,
                "score": score_result.overall,
                "tier": score_result.tier.name,
                "tier_color": score_result.tier.color,
                "findings_count": len(final_findings),
                "message": "Scan complete",
            })

    except (DownloadError, ExtractError, ValueError) as exc:
        safe_msg = str(exc) if isinstance(exc, ValueError) else f"Failed to acquire repository: {type(exc).__name__}"
        logger.error("scan_failed", scan_id=scan_id, error=str(exc))
        async with factory() as session:
            await update_scan_status(session, scan_id, ScanStatusEnum.FAILED, error_detail=safe_msg)
        await push_event(scan_id, {"status": "failed", "error": safe_msg})
    except Exception as exc:
        logger.error("scan_failed", scan_id=scan_id, error=str(exc), exc_info=True)
        safe_error = f"Analysis error: {str(exc)}" if get_settings().env == "local" else "An internal error occurred during scanning"
        async with factory() as session:
            await update_scan_status(session, scan_id, ScanStatusEnum.FAILED, error_detail=safe_error)
        await push_event(scan_id, {"status": "failed", "error": safe_error})


# ── Scanner integration ────────────────────────────────────────────────

async def _docker_image_available(image: str) -> bool:
    """Check if the Docker image is available locally without triggering remote pulls."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "image", "inspect", image,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=3.0)
        return proc.returncode == 0
    except Exception:
        return False


async def _run_scanners_docker(src_dir: Path, image: str) -> list[dict[str, Any]]:
    """Run scanners via the secure Docker sandbox (T-2.11)."""
    if not await _docker_image_available(image):
        logger.info("docker_scanner_image_missing", image=image)
        raise RuntimeError(f"Scanner image '{image}' is not available locally")

    out_dir = src_dir.parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "signals.json"

    cmd = [
        "docker", "run", "--rm",
        "--memory", "1g",
        "--cpus", "1.0",
        "--network", "none",
        "-v", f"{src_dir.absolute()}:/src:ro",
        "-v", f"{out_dir.absolute()}:/out:rw",
        image,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

    if process.returncode != 0:
        logger.warning("docker_scanner_failed", code=process.returncode, stderr=stderr.decode())
        raise RuntimeError(f"Docker scanner failed with code {process.returncode}")

    if out_file.exists():
        import json
        return json.loads(out_file.read_text())
    return []

async def _run_scanners(src_dir: Path, files: list) -> list[dict[str, Any]]:
    """Run available scanners."""
    settings = get_settings()
    
    # Try Docker sandbox first
    try:
        signals = await _run_scanners_docker(src_dir, settings.scanner_image)
        logger.info("docker_scanner_success", count=len(signals))
        return signals
    except Exception as exc:
        logger.warning("docker_scanner_error", error=str(exc), fallback="in_process")
        
    # Fallback to in-process (for local dev/demo without Docker)
    all_signals: list[dict[str, Any]] = []
    logs_dir = src_dir.parent / "scanner_logs"
    logs_dir.mkdir(exist_ok=True)

    try:
        import sys
        curr = Path(__file__).resolve()
        scanner_root = None
        for p in [curr] + list(curr.parents):
            cand = p / "scanner"
            if cand.is_dir():
                scanner_root = cand
                break
        if scanner_root and str(scanner_root) not in sys.path:
            sys.path.insert(0, str(scanner_root))

        from scanner_runner.bandit_runner import run_bandit
        from scanner_runner.eslint_runner import run_eslint
        from scanner_runner.gitleaks_runner import run_gitleaks
        from scanner_runner.lizard_runner import run_lizard
        from scanner_runner.radon_runner import run_radon
        from scanner_runner.normalizer import normalize_signals

        tools = [
            ("bandit", run_bandit),
            ("eslint", run_eslint),
            ("gitleaks", run_gitleaks),
            ("lizard", run_lizard),
            ("radon", run_radon),
        ]

        raw: list[dict[str, Any]] = []
        for tool_name, runner in tools:
            try:
                result = await asyncio.to_thread(runner, src_dir, logs_dir)
                if result.get("signals"):
                    raw.extend(result["signals"])
                    logger.info("scanner_done", tool=tool_name,
                                count=len(result["signals"]))
            except Exception as exc:
                logger.warning("scanner_failed", tool=tool_name, error=str(exc))

        all_signals = normalize_signals(raw)

    except ImportError as exc:
        logger.warning("scanner_import_failed", error=str(exc))

    return all_signals


def _signals_to_findings(
    signals: list[dict[str, Any]],
    src_dir: Path,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for i, sig in enumerate(signals):
        severity = sig.get("severity", "medium")
        confidence = sig.get("confidence", 0.5)

        snippet = sig.get("snippet", "")
        file_path = sig.get("file_path", "")
        line_start = sig.get("line_start", 1)
        line_end = sig.get("line_end", line_start)

        if not snippet and file_path:
            try:
                full_path = src_dir / file_path
                if full_path.is_file():
                    file_lines = full_path.read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines()
                    start_idx = max(0, line_start - 1)
                    end_idx = min(len(file_lines), line_end)
                    snippet = "\n".join(file_lines[start_idx:end_idx])
            except Exception:
                pass

        message = sig.get("message", "")
        tool = sig.get("tool", "scanner")
        rule = sig.get("rule_id", "")
        explanation = f"[{tool}:{rule}] {message}" if message else f"Issue detected by {tool}"

        findings.append({
            "rule_id": rule,
            "category": sig.get("category", "maintainability"),
            "severity": severity,
            "confidence": confidence,
            "message": message[:80] if message else explanation[:80],
            "explanation": explanation,
            "file": file_path,
            "line": line_start,
            "line_end": line_end,
            "snippet": snippet,
            "fingerprint": f"{tool}:{rule}:{file_path}:{line_start}",
            "tool": tool,
        })

    return findings


def _findings_to_scored(findings: list[dict[str, Any]]) -> list[ScoredSignal]:
    signals: list[ScoredSignal] = []
    for i, f in enumerate(findings):
        signals.append(ScoredSignal(
            signal_id=f.get("id", f"sig_{i}"),
            rule_id=f["rule_id"],
            category=f["category"],
            tool=f["tool"],
            severity=f["severity"],
            confidence=f["confidence"],
            file_path=f.get("file", "unknown"),
            line_start=f.get("line", 1),
            line_end=f.get("line_end", 1),
            occurrences=1,
            locations=[(f.get("file", ""), f.get("line", 1), f.get("line_end", 1))],
            primary_snippet=f.get("snippet", ""),
            risk_score=f["confidence"],
        ))
    return signals
