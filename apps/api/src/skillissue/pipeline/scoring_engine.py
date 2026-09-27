"""Real scoring engine per PRD §11.2-§11.6.

Implements the official formula:

  raw_c = Σ (w_sev(f) × confidence(f)) — over findings with confidence ≥ 0.50
  kloc  = max(0.5, LOC_analyzed / 1000)
  density_c = raw_c / sqrt(kloc)
  score_c = 100 × (1 − exp(−density_c / k_c)), rounded to nearest integer

Category weights (PRD §11.6):
  weighted = 0.35·security + 0.25·bugs + 0.15·maintainability
            + 0.10·performance + 0.15·hygiene

Floors (PRD §11.6):
  - Any critical security finding with confidence ≥ 0.80 → overall ≥ 60
  - Any verified live-format secret → overall ≥ 70

overall = round(max(weighted, applicable_floor)), clamped [0, 100]
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from skillissue.pipeline.score import ScoredSignal


# ── Pipeline version (PRD §11.8) ─────────────────────────────────────

PIPELINE_VERSION: str = "1.0.0"

# Initial defaults per PRD §11.4. Calibration may tune these in T-5.9.
_K_C: dict[str, float] = {
    "security": 20.0,
    "bugs": 25.0,
    "maintainability": 40.0,
    "performance": 40.0,
    "hygiene": 100.0,  # unused — hygiene uses checklist penalties, not exp curve
}


# ── Severity weights (PRD §11.2) ─────────────────────────────────────

SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 15.0,
    "high": 8.0,
    "medium": 3.0,
    "low": 1.0,
}


# ── Category weights (PRD §11.6) ─────────────────────────────────────

CATEGORY_WEIGHT: dict[str, float] = {
    "security": 0.35,
    "bugs": 0.25,
    "maintainability": 0.15,
    "performance": 0.10,
    "hygiene": 0.15,
}


# ── Tier thresholds (PRD FR-5.4) ────────────────────────────────────

@dataclass(frozen=True)
class Tier:
    """One rung on the cooked scale."""
    name: str
    min_score: int  # inclusive
    color: str
    glyph: str


TIERS: list[Tier] = [
    Tier("Raw",               0,  "#2B6CC4", "snowflake"),
    Tier("Lightly Toasted",  15,  "#3D8B40", "sun"),
    Tier("Medium Well",      35,  "#C9922B", "thermometer-sun"),
    Tier("Cooked",           60,  "#CF3626", "flame"),
    Tier("Burnt to a Crisp", 80,  "#4A2A22", "skull"),
]


# ── Hygiene penalties (PRD §11.5) ────────────────────────────────────

HYGIENE_PENALTIES: dict[str, int] = {
    "no_tests": 30,
    "no_ci": 15,
    "no_readme": 15,
    "thin_readme": 8,
    "no_license": 5,
    "no_gitignore": 10,
    "no_lockfile": 10,
    "no_linter": 5,
    "env_committed": 25,
}


# ── Confidence threshold (PRD §11.3) ─────────────────────────────────

MIN_CONFIDENCE_FOR_SCORING: float = 0.50


# ── Result dataclasses ───────────────────────────────────────────────

@dataclass(frozen=True)
class CategoryScore:
    """Score for one category."""
    name: str
    value: int            # 0–100, rounded
    raw: float            # raw_c (pre-normalization)
    density: float        # raw_c / sqrt(kloc)
    k_c: float            # the constant used


@dataclass(frozen=True)
class ScoreComponents:
    """All components of a final score, for reproducibility (PRD §11.8)."""
    overall: int                          # 0–100
    tier: Tier
    subscores: dict[str, CategoryScore]   # category → CategoryScore
    weighted_pre_floor: float             # weighted before floor
    floor_applied: int                    # floor that was applied (0 if none)
    loc_analyzed: int                     # LOC input
    hygiene_flags: list[str]
    kloc: float                           # max(0.5, LOC/1000)
    pipeline_version: str
    shown_findings: list[ScoredSignal]     # findings counted toward score
    tier_glyph: str = ""                  # mirroring Tier.glyph, for serialization
    tier_color: str = ""

    def to_dict(self) -> dict:
        """Serializable representation per PRD §11.8."""
        return {
            "overall": self.overall,
            "tier": self.tier.name,
            "tier_color": self.tier.color,
            "tier_glyph": self.tier.glyph,
            "weighted_pre_floor": round(self.weighted_pre_floor, 4),
            "floor_applied": self.floor_applied,
            "loc_analyzed": self.loc_analyzed,
            "kloc": round(self.kloc, 4),
            "pipeline_version": self.pipeline_version,
            "subscores": {
                name: {
                    "value": cs.value,
                    "raw": round(cs.raw, 4),
                    "density": round(cs.density, 4),
                    "k_c": cs.k_c,
                }
                for name, cs in self.subscores.items()
            },
            "hygiene_flags": self.hygiene_flags,
            "shown_findings": [
                {
                    "rule_id": s.rule_id,
                    "category": s.category,
                    "severity": s.severity,
                    "confidence": s.confidence,
                    "file_path": s.file_path,
                    "line_start": s.line_start,
                    "line_end": s.line_end,
                }
                for s in self.shown_findings
            ],
        }


# ── Tie-broken ranking (PRD FR-4.4) ──────────────────────────────────

_CATEGORY_PRIORITY: dict[str, int] = {
    "security": 0,
    "bugs": 1,
    "performance": 2,
    "maintainability": 3,
    "hygiene": 4,
}


def impact_rank_key(signal: ScoredSignal) -> tuple:
    """Sort key for impact_rank per FR-4.4 (severity × confidence, then category, then path)."""
    impact = SEVERITY_WEIGHT.get(signal.severity, 1.0) * signal.confidence
    cat_priority = _CATEGORY_PRIORITY.get(signal.category, 99)
    return (-impact, cat_priority, signal.file_path, signal.line_start)


def rank_findings(findings: list[ScoredSignal]) -> list[ScoredSignal]:
    """Sort by impact_rank desc, with deterministic tiebreaks."""
    return sorted(findings, key=impact_rank_key)


# ── Core math (PRD §11) ───────────────────────────────────────────────

def _round_half_up(x: float) -> int:
    """Half-up rounding per PRD §11.4."""
    return math.floor(x + 0.5)


def _compute_kloc(loc_analyzed: int) -> float:
    """kloc = max(0.5, LOC/1000) per PRD §11.4."""
    return max(0.5, loc_analyzed / 1000.0)


def _category_raw(
    findings: list[ScoredSignal],
    category: str,
    min_confidence: float = MIN_CONFIDENCE_FOR_SCORING,
) -> float:
    """Sum of (severity_weight × confidence) over findings with conf ≥ threshold."""
    total = 0.0
    for f in findings:
        if f.category != category:
            continue
        if f.confidence < min_confidence:
            continue
        w = SEVERITY_WEIGHT.get(f.severity, 1.0)
        total += w * f.confidence
    return total


def _category_score(
    findings: list[ScoredSignal],
    category: str,
    loc_analyzed: int,
) -> CategoryScore:
    """Compute one category's score per PRD §11.4."""
    raw = _category_raw(findings, category)
    kloc = _compute_kloc(loc_analyzed)
    density = raw / math.sqrt(kloc) if kloc > 0 else 0.0
    k_c = _K_C.get(category, 100.0)
    value = 100.0 * (1.0 - math.exp(-density / k_c))
    return CategoryScore(
        name=category,
        value=_round_half_up(value),
        raw=raw,
        density=density,
        k_c=k_c,
    )


def _hygiene_score(flags: list[str]) -> int:
    """Sum penalties (cap at 100) per PRD §11.5."""
    total = sum(HYGIENE_PENALTIES.get(f, 0) for f in flags)
    return min(100, total)


# ── Floors (PRD §11.6) ───────────────────────────────────────────────

def _compute_floor(findings: list[ScoredSignal], flags: list[str]) -> tuple[int, str]:
    """Return (floor_value, reason) per PRD §11.6.

    Two floors (highest-wins):
      - 70: verified live-format secret (gitleaks, critical, conf ≥ 0.50)
      - 60: critical security finding with confidence ≥ 0.80
      - 0: none apply
    """
    # Floor 2 (70): live secret — gitleaks with critical severity
    for f in findings:
        if f.tool == "gitleaks" and f.severity == "critical" and f.confidence >= 0.50:
            return 70, "live_secret"
    # Floor 1 (60): critical security with confidence ≥ 0.80
    for f in findings:
        if f.category == "security" and f.severity == "critical" and f.confidence >= 0.80:
            return 60, "critical_security"
    return 0, ""


# ── Tier lookup (PRD FR-5.4) ─────────────────────────────────────────

def score_to_tier(score: int) -> Tier:
    """Map score → Tier per PRD FR-5.4."""
    chosen = TIERS[0]
    for tier in TIERS:
        if score >= tier.min_score:
            chosen = tier
        else:
            break
    return chosen


# ── Top-level entry points ───────────────────────────────────────────

def compute_category_scores(
    findings: list[ScoredSignal],
    loc_analyzed: int,
) -> dict[str, CategoryScore]:
    """Per-category scores per PRD §11.4."""
    return {
        cat: _category_score(findings, cat, loc_analyzed)
        for cat in ("security", "bugs", "maintainability", "performance")
    }


def compute_overall(
    findings: list[ScoredSignal],
    loc_analyzed: int,
    hygiene_flags: list[str],
    *,
    pipeline_version: str = PIPELINE_VERSION,
) -> ScoreComponents:
    """Full score per PRD §11.4–§11.6.

    Args:
        findings: All deduplicated signals (with confidence ≥ 0.30 to survive
            prior filtering). Shown findings = confidence ≥ 0.50 (PRD §11.3).
        loc_analyzed: LOC that were analyzed (after filters).
        hygiene_flags: Hygiene flags from `pipeline.hygiene.check_all_hygiene`.
        pipeline_version: Defaults to module constant PIPELINE_VERSION.

    Returns:
        ScoreComponents with all scoring inputs captured for reproducibility.
    """
    # Show only findings with confidence ≥ 0.50 (PRD §11.3)
    shown = [f for f in findings if f.confidence >= MIN_CONFIDENCE_FOR_SCORING]

    # Rank per FR-4.4 — kept for caller use; not affecting the score itself
    shown_ranked = rank_findings(shown)

    # Per-category scores (PRD §11.4)
    subscores = compute_category_scores(shown_ranked, loc_analyzed)

    # Hygiene subscore (PRD §11.5)
    hygiene_value = _hygiene_score(hygiene_flags)
    subscores["hygiene"] = CategoryScore(
        name="hygiene",
        value=hygiene_value,
        raw=float(hygiene_value),
        density=0.0,
        k_c=100.0,  # hygiene doesn't use the exp curve
    )

    # Weighted score (PRD §11.6)
    weighted = sum(
        subscores[cat].value * CATEGORY_WEIGHT[cat]
        for cat in CATEGORY_WEIGHT
    )

    # Floors (PRD §11.6)
    floor_value, _floor_reason = _compute_floor(shown_ranked, hygiene_flags)

    # Combine and clamp
    overall = round(max(weighted, floor_value))
    overall = max(0, min(100, overall))

    tier = score_to_tier(overall)

    return ScoreComponents(
        overall=overall,
        tier=tier,
        subscores=subscores,
        weighted_pre_floor=weighted,
        floor_applied=floor_value,
        loc_analyzed=loc_analyzed,
        hygiene_flags=list(hygiene_flags),
        kloc=_compute_kloc(loc_analyzed),
        pipeline_version=pipeline_version,
        shown_findings=shown_ranked,
    )


# ── Summary sentence (PRD §11.6, FR-5.x copy) ──────────────────────

# Each row: (inclusive_upper, template). The first row whose upper is >= score wins.
SUMMARY_COPY: list[tuple[int, str]] = [
    (0,   "Barely touched by problems."),
    (14,  "Barely touched by problems — {n} minor notes."),
    (34,  "A few things to fix — {n} findings, none critical."),
    (59,  "Getting crispy. Prioritize the top issues — {n} findings."),
    (79,  "Serious problems. Start with the critical ones — {n} findings."),
    (100, "Stop shipping. Fix the security issues first — {n} findings."),
]


def summary_sentence(score: int, findings_count: int) -> str:
    """Pick one summary sentence for the score, per PRD §11.1 templates.

    Tier-bracketed copy per PRD FR-5.6. The 0–14 band uses a static copy
    (no {n} placeholder).
    """
    template = SUMMARY_COPY[0][1]
    for upper, text in SUMMARY_COPY:
        if score <= upper:
            template = text
            break
    if "{n}" in template:
        return template.format(n=findings_count)
    return template


def findings_to_score_input(
    findings_dicts: list,
    *,
    min_confidence: float = 0.30,
) -> list[ScoredSignal]:
    """Adapter: convert dict-shaped findings (e.g. from JSON scans) into ScoredSignals.

    Used when bootstrapping scoring from stored report findings.
    Non-dict inputs are silently skipped. Missing fields default sensibly.
    """
    out: list[ScoredSignal] = []
    for i, f in enumerate(findings_dicts):
        if not isinstance(f, dict):
            continue
        try:
            severity = f.get("severity", "medium")
            confidence = float(f.get("confidence", 0.5))
            if confidence < min_confidence:
                continue
            out.append(ScoredSignal(
                signal_id=f.get("signal_id", f"sig_{i}"),
                rule_id=f.get("rule_id", "unknown"),
                category=f.get("category", "maintainability"),
                tool=f.get("tool", "scanner"),
                severity=severity,
                confidence=confidence,
                file_path=f.get("file_path", f.get("file", "unknown")),
                line_start=int(f.get("line_start", 1)),
                line_end=int(f.get("line_end", 1)),
                occurrences=int(f.get("occurrences", 1)),
                locations=f.get("locations", []),
                primary_snippet=f.get("snippet", ""),
                risk_score=float(f.get("risk_score", confidence)),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return out
