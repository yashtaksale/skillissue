"""Repair configuration for actionable reports per ARCHITECTURE.md §7.4."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RepairConfig:
    """Configuration for generating repair suggestions."""

    # LLM call parameters (delegated to orchestrator)
    temperature: float = 0.2
    max_tokens: int = 2048

    # Scoring thresholds
    p1_risk_threshold: float = 0.80
    p2_risk_threshold: float = 0.55
    p3_risk_threshold: float = 0.30

    # Dedup
    primary_only: bool = True  # if True, send only P1/P2 locations to LLM

    def score_to_priority(self, risk_score: float) -> str:
        """Map risk score to priority label."""
        if risk_score >= self.p1_risk_threshold:
            return "P1"
        if risk_score >= self.p2_risk_threshold:
            return "P2"
        if risk_score >= self.p3_risk_threshold:
            return "P3"
        return "P4"


@dataclass(frozen=True)
class Finding:
    """A single finding in the analysis report."""

    rule_id: str
    category: str
    severity: str
    confidence: float
    priority: str
    file_path: str
    line_start: int
    line_end: int
    message: str
    snippet: str
    explanation: str
    fix: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "priority": self.priority,
            "file": self.file_path,
            "line": f"{self.line_start}-{self.line_end}",
            "message": self.message,
            "snippet": self.snippet,
            "explanation": self.explanation,
            "fix": self.fix,
        }


@dataclass(frozen=True)
class AnalysisReport:
    """Final report produced by the analysis pipeline."""

    repo_full_name: str
    ref: str | None
    files_scanned: int
    loc_total: int
    loc_supported: int
    coverage: str  # "full", "partial", "reduced_coverage", "hygiene_only"
    findings: list[Finding] = field(default_factory=list)
    hygiene_flags: list[str] = field(default_factory=list)
    llm_used: bool = False
    error: str | None = None

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def p1_count(self) -> int:
        return sum(1 for f in self.findings if f.priority == "P1")

    @property
    def p2_count(self) -> int:
        return sum(1 for f in self.findings if f.priority == "P2")

    @property
    def security_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.category == "security"]

    def to_dict(self) -> dict:
        return {
            "repo": self.repo_full_name,
            "ref": self.ref,
            "coverage": self.coverage,
            "files_scanned": self.files_scanned,
            "loc_total": self.loc_total,
            "loc_supported": self.loc_supported,
            "findings_count": self.total_findings,
            "p1_count": self.p1_count,
            "p2_count": self.p2_count,
            "security_count": len(self.security_findings),
            "hygiene_flags": self.hygiene_flags,
            "findings": [f.to_dict() for f in self.findings[:50]],
            "llm_used": self.llm_used,
            "error": self.error,
        }
