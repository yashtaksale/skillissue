"""Signal scoring and deduplication per ARCHITECTURE.md §7.4."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum


# === Severity and confidence levels ===


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Weight for deduplication score aggregation
_SEVERITY_WEIGHT: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Category mapping for tool→category
_TOOL_CATEGORY: dict[str, str] = {
    "semgrep": "semgrep",
    "bandit": "bandit",
    "eslint": "eslint",
    "gitleaks": "gitleaks",
    "lizard": "complexity",
    "radon": "complexity",
}


@dataclass(frozen=True)
class ScoredSignal:
    """A deduplicated and scored signal ready for LLM analysis."""
    signal_id: str
    rule_id: str
    category: str
    tool: str
    severity: str
    confidence: float
    file_path: str
    line_start: int
    line_end: int
    occurrences: int
    locations: list[tuple[str, int, int]]
    primary_snippet: str
    risk_score: float  # 0.0-1.0

    @property
    def weight(self) -> int:
        return _SEVERITY_WEIGHT.get(self.severity, 1)

    @property
    def is_security(self) -> bool:
        return self.category == "security"

    @property
    def priority(self) -> str:
        """Simple priority label for downstream consumers."""
        if self.severity in ("critical", "high") and self.confidence >= 0.8:
            return "P1"
        if self.severity == "high" or (self.severity == "medium" and self.confidence >= 0.7):
            return "P2"
        if self.severity == "medium":
            return "P3"
        return "P4"


def deduplicate_signals(signals: list[dict]) -> list[ScoredSignal]:
    """Deduplicate signals by (file_path, rule_id, line_start).

    Aggregates confidence by weighted average and counts occurrences.
    Keeps first occurrence's snippet as primary.

    Args:
        signals: List of raw signal dicts.

    Returns:
        List of ScoredSignal objects, sorted by risk_score descending.
    """
    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for sig in signals:
        key = (sig["file_path"], sig["rule_id"], sig["line_start"])
        groups[key].append(sig)

    scored: list[ScoredSignal] = []
    for key, group in groups.items():
        file_path, rule_id, line_start = key
        locations = [(s["file_path"], s["line_start"], s["line_end"]) for s in group]

        # Weighted average confidence
        total_weight = sum(_SEVERITY_WEIGHT.get(s["severity"], 1) for s in group)
        avg_confidence = sum(
            s["confidence"] * _SEVERITY_WEIGHT.get(s["severity"], 1) for s in group
        ) / total_weight if total_weight > 0 else 0.0

        # Risk score: 0.5 * confidence + 0.5 * (occurrences / max_occurrences)
        risk_score = min(1.0, avg_confidence * 0.5 + (len(group) / 10) * 0.5)

        primary = group[0]
        filename = Path(file_path).name
        signal_id = f"{_TOOL_CATEGORY.get(primary.get('tool', ''), 'unknown')}:{rule_id}:{filename}"

        scored.append(ScoredSignal(
            signal_id=signal_id,
            rule_id=rule_id,
            category=primary["category"],
            tool=primary["tool"],
            severity=primary["severity"],
            confidence=avg_confidence,
            file_path=file_path,
            line_start=line_start,
            line_end=primary["line_end"],
            occurrences=len(group),
            locations=locations,
            primary_snippet=primary.get("snippet", ""),
            risk_score=risk_score,
        ))

    # Sort by risk_score descending, then severity weight descending
    scored.sort(key=lambda s: (s.risk_score, s.weight), reverse=True)
    return scored


def filter_low_confidence(signals: list[ScoredSignal], min_confidence: float = 0.3) -> list[ScoredSignal]:
    """Remove signals below the confidence threshold."""
    return [s for s in signals if s.confidence >= min_confidence]


def score_signals(signals: list[ScoredSignal]) -> list[ScoredSignal]:
    """Recompute risk scores after dedup (no-op for now, placeholder for future scoring).

    Returns the input list with updated risk scores if needed.
    """
    return signals


def build_ranking(signals: list[ScoredSignal], max_signals: int = 50) -> list[ScoredSignal]:
    """Build a ranked list of signals for LLM analysis, limited to max_signals.

    Returns up to max_signals signals sorted by risk_score descending.
    """
    sorted_signals = sorted(signals, key=lambda s: s.risk_score, reverse=True)
    return sorted_signals[:max_signals]
