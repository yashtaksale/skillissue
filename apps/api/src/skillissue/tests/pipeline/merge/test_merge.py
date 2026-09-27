"""Tests for T-5.1 (Merge) and T-5.2 (Score normalization).

Covers:
- Scanner-only → unchanged
- LLM-only → converted and included
- Scanner + LLM at same (file, rule) → LLM replaces scanner
- Dedup within scanner signals (keep higher risk_score)
- Visibility cap (max_visible)
- has_live_secret()
- Dict-shaped findings
- Empty inputs
"""
from __future__ import annotations

import pytest

from skillissue.pipeline.merge import (
    MAX_VISIBLE,
    has_live_secret,
    merge_signals,
    _finding_output_to_signal,
    _dict_to_signal,
)
from skillissue.pipeline.score import ScoredSignal
from skillissue.pipeline.llm.schema import FindingOutput


# ── helpers ──────────────────────────────────────────────────────────

def _s(**kw):
    defaults = dict(
        signal_id="s1", rule_id="semgrep:sql-injection", category="security",
        tool="semgrep", severity="high", confidence=0.9, file_path="src/db.py",
        line_start=10, line_end=20, occurrences=1, locations=[],
        primary_snippet="cursor.execute(...)", risk_score=0.9,
    )
    defaults.update(kw)
    return ScoredSignal(**defaults)


def _fo(**kw):
    defaults = dict(
        signal_id="llm:0",
        rule_id="semgrep:sql-injection",
        category="security",
        severity="high",
        confidence=0.85,
        file_path="src/db.py",
        line_start=10,
        line_end=20,
        message="Potential SQL injection",
        explanation="User input reaches execute() without sanitization.",
        fix="Use parameterized queries.",
    )
    defaults.update(kw)
    return FindingOutput(**defaults)


# =====================================================================
# T-5.1 — Scanner-only
# =====================================================================

class TestScannerOnly:
    def test_passthrough(self):
        sigs = [_s(), _s(rule_id="bandit:hardcoded-password")]
        out = merge_signals(sigs, llm_findings=None)
        assert len(out) == 2
        rule_ids = {s.rule_id for s in out}
        assert "semgrep:sql-injection" in rule_ids
        assert "bandit:hardcoded-password" in rule_ids

    def test_empty_scanner(self):
        out = merge_signals([], llm_findings=None)
        assert out == []


# =====================================================================
# T-5.1 — LLM-only
# =====================================================================

class TestLLMOnly:
    def test_llm_added(self):
        llm = [_fo(rule_id="llm:complexity")]
        out = merge_signals([], llm_findings=llm)
        assert len(out) == 1
        assert out[0].rule_id == "llm:complexity"
        assert out[0].tool == "llm"

    def test_llm_uses_llm_confidence(self):
        llm = [_fo(confidence=0.3)]
        out = merge_signals([], llm_findings=llm)
        assert out[0].confidence == 0.3

    def test_empty_llm(self):
        out = merge_signals([], llm_findings=[])
        assert out == []


# =====================================================================
# T-5.1 — Merge / dedup
# =====================================================================

class TestMergeDedup:
    def test_llm_replaces_scanner_same_key(self):
        """LLM finding at same (file, rule_id) replaces scanner signal."""
        scanner = [_s(confidence=0.95)]  # scanner says high confidence
        llm = [_fo(confidence=0.7)]     # LLM says lower but more actionable
        out = merge_signals(scanner, llm_findings=llm)
        assert len(out) == 1
        assert out[0].tool == "llm"  # LLM replaces scanner

    def test_scanner_kept_when_no_llm_match(self):
        scanner = [_s()]
        llm = [_fo(rule_id="different-rule", file_path="other.py")]
        out = merge_signals(scanner, llm_findings=llm)
        # scanner is not overwritten
        scanner_sig = [s for s in out if s.rule_id == "semgrep:sql-injection"]
        assert len(scanner_sig) == 1
        assert scanner_sig[0].tool == "semgrep"

    def test_scanner_duplicate_keep_higher_risk(self):
        """Within scanner signals, keep the higher risk_score."""
        s1 = _s(risk_score=0.5)
        s2 = _s(risk_score=0.9)
        out = merge_signals([s1, s2])
        # Both kept at same key — but we have same (file, rule), so one wins
        assert len(out) == 1
        assert out[0].risk_score == 0.9

    def test_dict_input(self):
        """LLM findings can also be plain dicts."""
        scanner = [_s()]
        llm = [{"rule_id": "r1", "category": "bugs", "severity": "medium",
                "confidence": 0.6, "file_path": "f.py", "line_start": 1,
                "line_end": 5}]
        out = merge_signals(scanner, llm_findings=llm)
        assert len(out) == 2
        rule_ids = {s.rule_id for s in out}
        assert "r1" in rule_ids

    def test_dict_missing_fields_skipped(self):
        """Malformed dict inputs are skipped."""
        scanner = [_s()]
        llm = ["not_a_dict", {"rule_id": "r1", "category": "bugs", "severity": "medium", "confidence": 0.5, "file_path": "f.py", "line_start": 1, "line_end": 1}]
        out = merge_signals(scanner, llm_findings=llm)
        assert len(out) == 2  # scanner + valid dict

    def test_llm_finding_has_explanation(self):
        """LLM signal captures the explanation as snippet."""
        llm = [_fo(explanation="This is a real SQL injection risk.")]
        out = merge_signals([], llm_findings=llm)
        assert "SQL injection" in out[0].primary_snippet


# =====================================================================
# T-5.2 — Visibility cap
# =====================================================================

class TestVisibilityCap:
    def test_capped_at_max(self):
        scanner = [_s(rule_id=f"r{i}", confidence=i / 100.0) for i in range(100)]
        out = merge_signals(scanner, max_visible=MAX_VISIBLE)
        assert len(out) <= MAX_VISIBLE

    def test_unchanged_when_under_cap(self):
        scanner = [_s(rule_id=f"semgrep:r{i}", file_path=f"src/f{i}.py") for i in range(10)]
        out = merge_signals(scanner, max_visible=50)
        assert len(out) == 10


# =====================================================================
# has_live_secret
# =====================================================================

class TestHasLiveSecret:
    def test_gitleaks_critical(self):
        sigs = [_s(tool="gitleaks", severity="critical", confidence=0.9)]
        assert has_live_secret(sigs) is True

    def test_gitleaks_high_not_floor(self):
        sigs = [_s(tool="gitleaks", severity="high", confidence=0.9)]
        assert has_live_secret(sigs) is False

    def test_semgrep_critical_not_floor(self):
        sigs = [_s(tool="semgrep", severity="critical", confidence=0.9)]
        assert has_live_secret(sigs) is False

    def test_no_low_confidence(self):
        sigs = [_s(tool="gitleaks", severity="critical", confidence=0.3)]
        assert has_live_secret(sigs) is False

    def test_empty(self):
        assert has_live_secret([]) is False


# =====================================================================
# Adapter functions
# =====================================================================

class TestAdapter:
    def test_finding_output_to_signal(self):
        fo = _fo()
        sig = _finding_output_to_signal(fo, seq=0)
        assert sig.file_path == "src/db.py"
        assert sig.rule_id == "semgrep:sql-injection"
        assert sig.tool == "llm"
        assert sig.severity == "high"
        assert sig.confidence == 0.85

    def test_dict_to_signal(self):
        d = {"rule_id": "r1", "severity": "low", "confidence": 0.4,
             "file_path": "x.py", "line_start": 5, "line_end": 10,
             "category": "bugs"}
        sig = _dict_to_signal(d, seq=0)
        assert sig is not None
        assert sig.rule_id == "r1"
        assert sig.severity == "low"

    def test_dict_to_signal_missing_rule_id(self):
        d = {"severity": "low"}  # no file_path, no line_start
        sig = _dict_to_signal(d, seq=0)
        # missing file_path and line_start are handled with defaults
        assert sig is not None

    def test_dict_to_signal_malformed(self):
        d = "not a dict"
        sig = _dict_to_signal(d, seq=0)  # type: ignore[arg-type]
        assert sig is None
