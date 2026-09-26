"""Real scoring engine per PRD §11.2 and §11.3."""
from __future__ import annotations

import math

from skillissue.pipeline.score import ScoredSignal

# ── Severity weights ────────────────────────────────────────────────

_SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}

# ── k_c per category (PRD §11.2 table) ─────────────────────────────

_K_C: dict[str, float] = {
    "security": 2.0,
    "bugs": 3.0,
    "maintainability": 5.0,
    "performance": 4.0,
    "hygiene": 8.0,
}

# ── Category weights ────────────────────────────────────────────────

_CATEGORY_WEIGHT: dict[str, float] = {
    "security": 0.35,
    "bugs": 0.25,
    "maintainability": 0.15,
    "performance": 0.10,
    "hygiene": 0.15,
}

# ── Tier thresholds ────────────────────────────────────────────────

_TIERS = [
    (0,   "Raw",                   "#2B6CC4", "snowflake"),
    (15,  "Lightly Toasted",       "#3D8B40", "sun"),
    (35,  "Medium Well",           "#C9922B", "thermometer-sun"),
    (60,  "Cooked",                "#CF3626", "flame"),
    (80,  "Burnt to a Crisp",      "#4A2A22", "skull"),
]

# ── Floors ─────────────────────────────────────────────────────────

def _compute_floor(findings: list[ScoredSignal]) -> int:
    has_p1_security = any(
        f.priority == "P1" and f.is_security for f in findings
    )
    has_p1 = any(f.priority == "P1" for f in findings)
    has_p2_security = any(
        f.priority == "P2" and f.is_security for f in findings
    )
    if has_p1_security:
        return 60
    if has_p1:
        return 45
    if has_p2_security:
        return 30
    return 0


def score_to_tier(score: int) -> tuple[str, str, str]:
    """Return (tier_name, color, glyph) for a score."""
    prev = ("Raw", "#2B6CC4", "snowflake")
    for threshold, name, color, glyph in _TIERS:
        if score < threshold:
            return prev
        prev = (name, color, glyph)
    return prev


def compute_category_scores(findings: list[ScoredSignal]) -> dict[str, float]:
    """Compute per-category raw scores using the PRD formula."""
    result: dict[str, float] = {}
    for category, weight in _CATEGORY_WEIGHT.items():
        cat_findings = [f for f in findings if f.category == category]
        density = sum(f.confidence * f.weight for f in cat_findings)
        k_c = _K_C.get(category, 5.0)
        result[category] = round(100.0 * (1.0 - math.exp(-density / k_c)))
    return result


def compute_overall_score(cat_scores: dict[str, float], floor: int) -> int:
    """Blend category scores with weights, apply floor, clamp [0, 100]."""
    weighted = sum(
        cat_scores.get(cat, 0) * w for cat, w in _CATEGORY_WEIGHT.items()
    )
    overall = round(max(weighted, floor))
    return max(0, min(100, overall))


def summary_sentence(score: int, tier: str, findings_count: int) -> str:
    """One-line summary per PRD §11.5."""
    if score == 0:
        return "No significant issues detected. Keep it clean."
    if score <= 14:
        return f"Barely touched by problems — {findings_count} minor notes."
    if score <= 34:
        return f"A few things to fix — {findings_count} findings, none critical."
    if score <= 59:
        return f"Needs attention — {findings_count} findings including high-severity items."
    if score <= 79:
        return f"Serious problems. Start with the critical and high-severity findings."
    return "Stop shipping. Fix the security issues first."
