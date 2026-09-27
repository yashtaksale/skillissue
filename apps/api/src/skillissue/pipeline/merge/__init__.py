"""Merge scanner signals and LLM findings into a clean ScoredSignal list.

T-5.1: Merge
  - Convert FindingOutput (LLM) → ScoredSignal
  - Deduplicate: scanner + LLM signals with matching (file_path, rule_id)
    are merged (LLM finding replaces the scanner signal).
  - Sort by impact_rank.

T-5.2: Score normalization
  - Visibility cap: at most max_visible findings overall (PRD FR-5.2: 50).
  - Produce the ranked list consumed by scoring_engine.compute_overall.
"""
from __future__ import annotations

from skillissue.pipeline.llm.schema import FindingOutput
from skillissue.pipeline.score import ScoredSignal, build_ranking


# ── Constants ────────────────────────────────────────────────────────

#: Cap on shown findings (PRD FR-5.2: report shows top 50 findings).
MAX_VISIBLE: int = 50

#: Scanners that detect hardcoded secrets (PRD §11.6: live secret floor).
_SECRET_SCANNERS: frozenset[str] = frozenset({"gitleaks"})


# ── LLM → ScoredSignal adapter ───────────────────────────────────────

def _finding_output_to_signal(
    finding: FindingOutput,
    *,
    seq: int,
) -> ScoredSignal:
    """Convert a FindingOutput from the LLM into a ScoredSignal.

    The LLM assigns confidence directly (0.0–1.0) and produces
    explanation + fix, which are more actionable than raw scanner signals.
    We keep the LLM's confidence as-is.

    Args:
        finding: LLM-produced finding.
        seq: Sequence number for unique signal_id generation.

    Returns:
        A ScoredSignal ready for dedup + scoring.
    """
    return ScoredSignal(
        signal_id=f"llm:{seq}",
        rule_id=finding.rule_id,
        category=finding.category,
        tool="llm",
        severity=finding.severity,
        confidence=finding.confidence,
        file_path=finding.file_path,
        line_start=finding.line_start,
        line_end=finding.line_end,
        occurrences=1,
        locations=[(finding.file_path, finding.line_start, finding.line_end)],
        primary_snippet=finding.message[:500],
        risk_score=finding.confidence,
    )


def _dict_to_signal(d: dict, *, seq: int) -> ScoredSignal | None:
    """Convert a dict-shaped finding to a ScoredSignal.

    Handles both flat dicts (from JSON storage) and FindingOutput dumps.
    Returns None if the dict is missing required fields.
    """
    if not isinstance(d, dict):
        return None
    try:
        severity = d.get("severity", "medium")
        confidence = float(d.get("confidence", 0.5))
        category = d.get("category", "maintainability")
        rule_id = d.get("rule_id", "unknown")
        file_path = d.get("file_path", d.get("file", "unknown"))
        line_start = int(d.get("line_start", 1))
        line_end = int(d.get("line_end", line_start))
        snippet = d.get("snippet", d.get("primary_snippet", d.get("message", "")))
        tool = d.get("tool", "llm")

        return ScoredSignal(
            signal_id=f"llm:{seq}",
            rule_id=rule_id,
            category=category,
            tool=tool,
            severity=severity,
            confidence=confidence,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            occurrences=1,
            locations=[(file_path, line_start, line_end)],
            primary_snippet=snippet[:500] if snippet else "",
            risk_score=confidence,
        )
    except (KeyError, ValueError, TypeError):
        return None


# ── Deduplication key ────────────────────────────────────────────────

def _dedup_key(signal: ScoredSignal) -> tuple[str, str]:
    """Key for dedup: (file_path, rule_id)."""
    return (signal.file_path, signal.rule_id)


# ── Merge ────────────────────────────────────────────────────────────

def merge_signals(
    scanner_signals: list[ScoredSignal],
    llm_findings: list[FindingOutput] | list[dict] | None = None,
    *,
    max_visible: int = MAX_VISIBLE,
) -> list[ScoredSignal]:
    """Merge scanner signals and LLM findings into a deduplicated list.

    Dedup policy:
    - Scanner-only signals: kept as-is.
    - LLM-only findings: converted to ScoredSignal.
    - Scanner + LLM at same (file_path, rule_id): the LLM finding
      replaces the scanner signal because it carries an explanation
      and fix, which are more actionable.

    Args:
        scanner_signals: Pre-scored scanner output.
        llm_findings: LLM analysis results (FindingOutput, dict, or None).
        max_visible: Cap on returned findings for scoring.

    Returns:
        Merged, deduplicated, ranked list of ScoredSignal objects.
    """
    # Step 1: index scanner signals by dedup key
    scanner_by_key: dict[tuple[str, str], ScoredSignal] = {}
    for sig in scanner_signals:
        key = _dedup_key(sig)
        if key not in scanner_by_key or sig.risk_score > scanner_by_key[key].risk_score:
            scanner_by_key[key] = sig

    # Step 2: convert LLM findings
    llm_signals: list[ScoredSignal] = []
    if llm_findings:
        seq = 0
        for raw in llm_findings:
            # Only process dict and FindingOutput; skip everything else
            if isinstance(raw, dict):
                signal = _dict_to_signal(raw, seq=seq)
            elif isinstance(raw, FindingOutput):
                signal = _finding_output_to_signal(raw, seq=seq)
            else:
                seq += 1
                continue
            if signal is not None:
                llm_signals.append(signal)
            seq += 1

    # Step 3: dedup — LLM replaces scanner at same key
    llm_by_key: dict[tuple[str, str], ScoredSignal] = {}
    for sig in llm_signals:
        key = _dedup_key(sig)
        if key not in llm_by_key or sig.risk_score > llm_by_key[key].risk_score:
            llm_by_key[key] = sig

    merged: list[ScoredSignal] = []
    # Scanner-only (not overwritten by LLM)
    for key, sig in scanner_by_key.items():
        if key not in llm_by_key:
            merged.append(sig)
    # All LLM findings (they replace scanner where keys collide)
    for sig in llm_by_key.values():
        merged.append(sig)

    # Step 4: rank and cap
    ranked = build_ranking(merged, max_signals=max_visible)
    return ranked


def has_live_secret(findings: list[ScoredSignal]) -> bool:
    """Return True if any finding is a verified live-format secret.

    PRD §11.6: a verified live-format secret (gitleaks, critical, conf ≥ 0.50)
    triggers a floor of 70 on the overall score.
    """
    return any(
        f.tool in _SECRET_SCANNERS
        and f.severity == "critical"
        and f.confidence >= 0.50
        for f in findings
    )
