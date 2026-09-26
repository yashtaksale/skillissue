"""Greedy file selector with diversity constraints (T-3.4).

Strategy:
1. Forced inclusion: files with medium+ scanner signals are always included.
2. Forced inclusion: entrypoint files are always included.
3. Diversity: penalize selecting many files from the same directory.
4. Greedy fill: select remaining files by score, respecting budget.
5. Forced include: every chunk holding medium+ signals (enforced by scoring).

Budget constraints (per PRD §7.6 / TASK.md T-3.4):
  - Max 30 chunks
  - Max 150k tokens total
  - Diversity: no single directory exceeds 60% of any chunk's files
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillissue.pipeline.sample.chunker import Chunk, ChunkBudget
from skillissue.pipeline.sample.scorer import FileScore


# =====================================================================
# Signal info (from scanner pipeline)
# =====================================================================


@dataclass(frozen=True)
class SignalInfo:
    """A scanner signal that maps to a specific file."""

    signal_id: str
    file: str
    severity: str         # critical | high | medium | low
    category: str         # security | bugs | performance | maintainability
    line_start: int = 0
    line_end: int = 0


_SIGNAL_SEVERITY_BOOST: dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.1,
}


# =====================================================================
# Diversity constraint
# =====================================================================


def _dir_key(path: str) -> str:
    """Get the parent directory of a path."""
    return str(Path(path).parent)


def _dir_penalty(path: str, chunk_files: list[str]) -> float:
    """Compute a diversity penalty for adding a file to a chunk.

    Penalty increases as more files from the same directory accumulate.
    Capped so a directory never exceeds 60% of chunk files.
    """
    d = _dir_key(path)
    same_dir = sum(1 for f in chunk_files if _dir_key(f) == d)
    total = len(chunk_files) + 1
    if total == 0:
        return 0.0
    ratio = (same_dir + 1) / (total + 1)
    if ratio > 0.6:
        # Hard penalty: we're over the diversity threshold
        return 0.5
    return 0.0


# =====================================================================
# Deterministic tiebreaker
# =====================================================================


def _stable_seed(path: str) -> int:
    """Stable hash for deterministic tie-breaking."""
    return int(hashlib.md5(path.encode()).hexdigest()[:8], 16)


# =====================================================================
# Greedy selector (T-3.4)
# =====================================================================


@dataclass
class SelectorConfig:
    """Configuration for the greedy selector."""

    max_chunks: int = 30
    max_tokens: int = 150_000
    max_files_per_chunk: int = 50
    overlap_lines: int = 20
    diversity_penalty: float = 0.3
    min_signal_severity: str = "medium"  # signals at this level force inclusion


def select_files(
    scores: list[FileScore],
    *,
    signals: list[SignalInfo] | None = None,
    source_dir: Path | str | None = None,
    config: SelectorConfig | None = None,
) -> tuple[list[Chunk], list[str]]:
    """Select files for LLM analysis and produce chunks.

    Args:
        scores: FileScore list from T-3.3 (sorted by score, highest first).
        signals: Scanner signals mapped to files.
        source_dir: Root directory for rendering.
        config: Selector configuration.

    Returns:
        (chunks, unselected_paths) — chunks ready for LLM, unselected files.
    """
    config = config or SelectorConfig()
    source_dir = Path(source_dir) if source_dir else None
    signals = signals or []

    # 1. Identify forced-inclusion files (T-3.4 requirement)
    signal_files: set[str] = set()
    signal_severity: dict[str, str] = {}
    for sig in signals:
        if _SIGNAL_SEVERITY_BOOST.get(sig.severity, 0) >= _SIGNAL_SEVERITY_BOOST.get(
            config.min_signal_severity, 0.4
        ):
            signal_files.add(sig.file)
            signal_severity[sig.file] = sig.severity

    entrypoint_files = {fs.path for fs in scores if fs.is_entrypoint}

    forced = signal_files | entrypoint_files
    remaining = [fs for fs in scores if fs.path not in forced]

    # 2. Greedy selection with diversity
    selected: list[str] = list(forced)  # forced first (preserve order from scores)
    chunks: list[Chunk] = []
    token_used = 0
    chunk_token_budget = config.max_tokens // config.max_chunks

    def _can_fit(path: str, fs: FileScore, chunk_files: list[str]) -> bool:
        """Check if a file fits in the current chunk."""
        nonlocal token_used
        if len(chunk_files) >= config.max_files_per_chunk:
            return False
        if token_used + fs.estimated_tokens > chunk_token_budget:
            return False
        return True

    # Build chunks from forced + greedy fill
    current_chunk_files: list[str] = []
    current_chunk_tokens = 0
    dir_counts: dict[str, int] = defaultdict(int)

    def _flush_chunk() -> None:
        nonlocal current_chunk_files, current_chunk_tokens, dir_counts, token_used
        if not current_chunk_files:
            return

        total_lines = sum(fs.lines for p in current_chunk_files for fs in scores if fs.path == p)
        total_bytes = sum(fs.estimated_tokens * 3 for p in current_chunk_files for fs in scores if fs.path == p)

        chunks.append(Chunk(
            chunk_id=len(chunks),
            files=list(current_chunk_files),
            total_lines=total_lines,
            total_bytes=total_bytes,
            estimated_tokens=current_chunk_tokens,
            selection_reason=_chunk_reason(current_chunk_files, signal_files, scores),
        ))
        token_used += current_chunk_tokens
        current_chunk_files = []
        current_chunk_tokens = 0
        dir_counts.clear()

    # Add forced files first
    for path in forced:
        fs = next((s for s in scores if s.path == path), None)
        if fs is None:
            continue

        if len(current_chunk_files) >= config.max_files_per_chunk:
            _flush_chunk()

        current_chunk_files.append(path)
        current_chunk_tokens += fs.estimated_tokens
        dir_counts[_dir_key(path)] += 1

        if current_chunk_tokens >= chunk_token_budget:
            _flush_chunk()

    # Flush any partial forced chunk
    _flush_chunk()

    # 3. Greedy fill: highest score first, with hard diversity constraint
    for fs in remaining:
        if len(chunks) >= config.max_chunks:
            break
        if token_used + fs.estimated_tokens > config.max_tokens:
            break

        if len(current_chunk_files) >= config.max_files_per_chunk:
            _flush_chunk()

        # Hard diversity constraint: no dir > 60% of chunk files
        d = _dir_key(fs.path)
        new_total = len(current_chunk_files) + 1
        same_dir = dir_counts[d] + 1
        if (same_dir / new_total) > 0.6 and current_chunk_files:
            # Flush current chunk to start fresh for this file
            _flush_chunk()
            # Safety: if the very first file in a chunk violates, we still add it
            # (a single file can't violate the 60% constraint meaningfully)

        current_chunk_files.append(fs.path)
        current_chunk_tokens += fs.estimated_tokens
        selected.append(fs.path)
        dir_counts[_dir_key(fs.path)] += 1

        if current_chunk_tokens >= chunk_token_budget:
            _flush_chunk()

    # Final flush
    _flush_chunk()

    unselected = [fs.path for fs in scores if fs.path not in selected]
    return chunks, unselected


def _chunk_reason(
    files: list[str],
    signal_files: set[str],
    scores: list[FileScore],
) -> str:
    """Build a human-readable selection reason for a chunk."""
    reasons: list[str] = []
    if any(f in signal_files for f in files):
        reasons.append("has scanner signals")
    entry = any(
        any(fs.is_entrypoint for fs in scores if fs.path == fp)
        for fp in files
    )
    if entry:
        reasons.append("entrypoints")
    risk = any(fs.risk_score >= 0.5 for fp in files for fs in scores if fs.path == fp)
    if risk:
        reasons.append("risk paths")
    if not reasons:
        reasons.append("coverage")
    return ", ".join(reasons)


def force_include_signals(
    scores: list[FileScore],
    signals: list[SignalInfo],
) -> list[str]:
    """Return paths that must be included due to scanner signals.

    Files with medium+ severity signals are always included.
    """
    min_sev_boost = _SIGNAL_SEVERITY_BOOST.get("medium", 0.4)
    paths: set[str] = set()
    for sig in signals:
        if _SIGNAL_SEVERITY_BOOST.get(sig.severity, 0) >= min_sev_boost:
            paths.add(sig.file)
    return sorted(paths)
