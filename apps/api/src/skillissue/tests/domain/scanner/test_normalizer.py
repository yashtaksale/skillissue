"""Snapshot tests for tool-output normalizers.

Each test feeds a minimal but representative JSON fixture into the matching
normalizer and asserts the produced ``RawSignal`` objects match the expected
(category, severity, confidence, file, lines, snippet) — captured in tables
below.

Snapshots are intentionally inline (not in ``snapshots/``) so the test file
is self-contained and easy to scan.
"""
from __future__ import annotations

from dataclasses import asdict

import pytest

from skillissue.domain.scanner.models import RawSignal
from skillissue.domain.scanner.normalizer import (
    normalize_bandit,
    normalize_eslint,
    normalize_gitleaks,
    normalize_lizard,
    normalize_radon,
    normalize_semgrep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signal_summary(s: RawSignal) -> dict:
    """Convert a RawSignal to a comparison-friendly dict, excluding snippet."""
    d = asdict(s)
    d.pop("snippet")
    d.pop("signal_id")  # depends on test run; exclude from snapshot
    d.pop("meta")       # tool-specific; checked separately
    return d


def _meta_summary(s: RawSignal, keys: tuple[str, ...]) -> dict:
    """Pick a stable subset of meta keys for snapshotting."""
    return {k: s.meta.get(k) for k in keys}


# ---------------------------------------------------------------------------
# Semgrep
# ---------------------------------------------------------------------------

SEMGREP_INPUT = {
    "results": [
        {
            "check_id": "python.lang.security.audit.dangerous-system-call",
            "path": "src/app.py",
            "start": {"line": 10, "col": 1},
            "end": {"line": 12, "col": 5},
            "extra": {
                "severity": "ERROR",
                "metadata": {"cwe": ["CWE-78"], "owasp": ["A03:2021"]},
                "message": "Detected use of os.system()",
                "lines": "os.system(user_input)\n",
            },
        },
        {
            "check_id": "python.lang.best-practice.unused-import",
            "path": "src/utils.py",
            "start": {"line": 1, "col": 1},
            "end": {"line": 1, "col": 1},
            "extra": {
                "severity": "INFO",
                "message": "Unused import 'os'",
                "lines": "import os\n",
            },
        },
        {
            "check_id": "javascript.lang.security.audit.xss",
            "path": "web/page.ts",
            "start": {"line": 50, "col": 1},
            "end": {"line": 50, "col": 20},
            "extra": {
                "severity": "WARNING",
                "message": "Reflected XSS",
                "lines": "innerHTML = req.query.x;\n",
            },
        },
    ]
}


class TestNormalizeSemgrep:
    def test_emits_one_signal_per_result(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        assert len(signals) == 3
        assert all(isinstance(s, RawSignal) for s in signals)

    def test_error_maps_to_security_high(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        s = signals[0]
        assert s.tool == "semgrep"
        assert s.category == "security"
        assert s.severity == "high"
        assert s.confidence == pytest.approx(0.85)
        assert s.file_path == "src/app.py"
        assert s.line_start == 10
        assert s.line_end == 12

    def test_warning_maps_to_medium(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        s = signals[2]
        assert s.severity == "medium"
        assert s.confidence == pytest.approx(0.70)

    def test_info_maps_to_low(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        s = signals[1]
        assert s.severity == "low"
        assert s.confidence == pytest.approx(0.55)

    def test_meta_preserved(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        s = signals[0]
        assert s.meta.get("cwe") == ["CWE-78"]
        assert s.meta.get("owasp") == ["A03:2021"]

    def test_empty_output_returns_empty_list(self):
        assert normalize_semgrep({"results": []}) == []


# ---------------------------------------------------------------------------
# Bandit
# ---------------------------------------------------------------------------

BANDIT_INPUT = {
    "results": [
        {
            "test_name": "exec_used",
            "test_id": "B102",
            "issue_severity": "HIGH",
            "issue_confidence": "HIGH",
            "issue_text": "Use of exec detected.",
            "filename": "src/app.py",
            "line_range": [3, 5],
            "code": "exec(user_input)\n",
        },
        {
            "test_name": "assert_used",
            "test_id": "B101",
            "issue_severity": "LOW",
            "issue_confidence": "HIGH",
            "issue_text": "Use of assert detected.",
            "filename": "tests/test_x.py",
            "line_range": [10],
            "code": "assert x == 1\n",
        },
    ]
}


class TestNormalizeBandit:
    def test_emits_one_signal_per_result(self):
        signals = normalize_bandit(BANDIT_INPUT)
        assert len(signals) == 2

    def test_high_maps_to_security_high(self):
        signals = normalize_bandit(BANDIT_INPUT)
        s = signals[0]
        assert s.tool == "bandit"
        assert s.category == "security"
        assert s.severity == "high"
        assert s.confidence == pytest.approx(0.85)
        assert s.file_path == "src/app.py"
        assert s.line_start == 3
        assert s.line_end == 5

    def test_low_maps_to_security_low(self):
        signals = normalize_bandit(BANDIT_INPUT)
        s = signals[1]
        assert s.severity == "low"
        assert s.confidence == pytest.approx(0.55)

    def test_meta_includes_test_name(self):
        signals = normalize_bandit(BANDIT_INPUT)
        assert signals[0].meta["test_name"] == "exec_used"

    def test_empty_output(self):
        assert normalize_bandit({"results": []}) == []


# ---------------------------------------------------------------------------
# ESLint
# ---------------------------------------------------------------------------

ESLINT_INPUT = [
    {
        "filePath": "src/app.ts",
        "messages": [
            {
                "ruleId": "no-eval",
                "severity": 2,
                "message": "Unexpected eval().",
                "line": 7,
                "endLine": 7,
                "column": 1,
                "endColumn": 25,
                "nodeType": "CallExpression",
                "source": "eval(userInput);",
            },
            {
                "ruleId": "detect-object-injection",
                "severity": 2,
                "message": "Object injection.",
                "line": 15,
                "endLine": 15,
                "column": 5,
                "endColumn": 30,
                "source": "users[userId];",
            },
        ],
    }
]


class TestNormalizeEslint:
    def test_emits_one_signal_per_message(self):
        signals = normalize_eslint(ESLINT_INPUT)
        assert len(signals) == 2

    def test_non_noisy_rule_confidence_065(self):
        signals = normalize_eslint(ESLINT_INPUT)
        s = signals[0]
        assert s.tool == "eslint"
        assert s.category == "security"
        assert s.severity == "high"
        assert s.confidence == pytest.approx(0.65)
        assert s.file_path == "src/app.ts"
        assert s.line_start == 7

    def test_noisy_rule_confidence_045(self):
        signals = normalize_eslint(ESLINT_INPUT)
        s = signals[1]
        assert s.severity == "high"
        assert s.confidence == pytest.approx(0.45)
        assert s.rule_id == "detect-object-injection"

    def test_warning_severity_maps_to_medium(self):
        warnings = [{
            "filePath": "x.ts",
            "messages": [{
                "ruleId": "no-unused-vars",
                "severity": 1,
                "message": "x is unused",
                "line": 1,
                "endLine": 1,
            }],
        }]
        signals = normalize_eslint(warnings)
        assert signals[0].severity == "medium"
        # Non-noisy ESLint rules get default 0.65 confidence (noisy → 0.45).
        assert signals[0].confidence == pytest.approx(0.65)

    def test_empty_output(self):
        assert normalize_eslint([]) == []


# ---------------------------------------------------------------------------
# gitleaks
# ---------------------------------------------------------------------------

GITLEAKS_INPUT = [
    {
        "Description": "AWS Access Key",
        "Rule": "AWS",
        "Secret": "AKIAIOSFODNN7EXAMPLE",
        "File": "config/credentials",
        "Line": 42,
        "StartColumn": 5,
        "EndColumn": 25,
        "Commit": "abc123",
    },
    {
        "Description": "Generic API key",
        "Rule": "generic-api-key",
        "Secret": "abcdef1234567890",
        "File": "src/app.py",
        "Line": 10,
    },
]


class TestNormalizeGitleaks:
    def test_emits_one_signal_per_finding(self):
        signals = normalize_gitleaks(GITLEAKS_INPUT)
        assert len(signals) == 2

    def test_provider_rule_maps_to_critical(self):
        signals = normalize_gitleaks(GITLEAKS_INPUT)
        s = signals[0]
        assert s.tool == "gitleaks"
        assert s.category == "security"
        assert s.severity == "critical"
        assert s.confidence == pytest.approx(0.95)
        assert s.file_path == "config/credentials"
        assert s.line_start == 42

    def test_generic_rule_maps_to_high(self):
        signals = normalize_gitleaks(GITLEAKS_INPUT)
        s = signals[1]
        assert s.severity == "high"
        assert s.confidence == pytest.approx(0.70)

    def test_secret_is_masked_in_meta(self):
        signals = normalize_gitleaks(GITLEAKS_INPUT)
        masked = signals[0].meta["secret_masked"]
        # 20-char AWS key: 4 + 14 bullets + 2
        assert masked == "AKIA" + "•" * 14 + "LE"

    def test_empty_output(self):
        assert normalize_gitleaks([]) == []


# ---------------------------------------------------------------------------
# Lizard
# ---------------------------------------------------------------------------

LIZARD_INPUT = {
    "average_complexity": 8.4,
    "files": [
        {
            "filename": "src/app.py",
            "functions": [
                {
                    "name": "process",
                    "complexity": 35,    # >30 → medium
                    "start_line": 10,
                    "end_line": 80,
                    "length": 70,
                },
                {
                    "name": "helper",
                    "complexity": 18,    # >15 → low
                    "start_line": 90,
                    "end_line": 130,
                    "length": 40,
                },
                {
                    "name": "tiny",
                    "complexity": 2,
                    "start_line": 200,
                    "end_line": 210,
                    "length": 10,
                },
            ],
        },
        {
            "filename": "src/long.py",
            "functions": [
                {
                    "name": "huge",
                    "complexity": 4,
                    "start_line": 1,
                    "end_line": 250,
                    "length": 250,       # >200 → low maintainability
                },
            ],
        },
    ],
}


class TestNormalizeLizard:
    def test_emits_signals_for_thresholds(self):
        signals = normalize_lizard(LIZARD_INPUT)
        # process (CCN>30) + helper (CCN>15) + huge (length>200) = 3
        assert len(signals) == 3

    def test_ccn_over_30_maps_to_medium(self):
        signals = normalize_lizard(LIZARD_INPUT)
        s = next(x for x in signals if "process" in x.rule_id)
        assert s.category == "maintainability"
        assert s.severity == "medium"
        assert s.confidence == pytest.approx(0.95)
        assert s.line_start == 10
        assert s.line_end == 80

    def test_ccn_between_16_and_30_maps_to_medium(self):
        signals = normalize_lizard(LIZARD_INPUT)
        s = next(x for x in signals if "helper" in x.rule_id)
        assert s.category == "maintainability"
        assert s.severity == "medium"
        assert s.confidence == pytest.approx(0.95)
        assert s.line_start == 90
        assert s.line_end == 130

    def test_long_function_maps_to_low(self):
        signals = normalize_lizard(LIZARD_INPUT)
        s = next(x for x in signals if "huge" in x.rule_id)
        assert s.severity == "low"
        assert s.confidence == pytest.approx(0.90)

    def test_no_signal_for_below_thresholds(self):
        signals = normalize_lizard(LIZARD_INPUT)
        assert not any("tiny" in s.rule_id for s in signals)

    def test_empty_output(self):
        assert normalize_lizard({"files": []}) == []


# ---------------------------------------------------------------------------
# Radon
# ---------------------------------------------------------------------------

RADON_CC_INPUT = {
    "src/app.py": [
        {
            "type": "function",
            "name": "foo",
            "complexity": 35,
            "rank": "E",
            "line": 1,
            "endline": 20,
        },
        {
            "type": "method",
            "name": "bar",
            "complexity": 12,
            "rank": "D",
            "line": 30,
            "endline": 45,
        },
        {
            "type": "function",
            "name": "ok",
            "complexity": 3,
            "rank": "A",
            "line": 50,
            "endline": 55,
        },
    ],
}

RADON_MI_INPUT = {
    "src/big.py": {
        "mi": 42.5,
        "rank": "F",
    },
    "src/ok.py": {
        "mi": 80.0,
        "rank": "A",
    },
}


class TestNormalizeRadon:
    def test_cc_rank_e_maps_to_medium(self):
        signals = normalize_radon(RADON_CC_INPUT)
        s = signals[0]
        assert s.tool == "radon"
        assert s.category == "maintainability"
        assert s.severity == "medium"
        assert s.confidence == pytest.approx(0.90)
        assert s.file_path == "src/app.py"
        assert s.line_start == 1

    def test_cc_rank_d_maps_to_low(self):
        signals = normalize_radon(RADON_CC_INPUT)
        s = signals[1]
        assert s.severity == "low"
        assert s.confidence == pytest.approx(0.90)

    def test_cc_rank_a_ignored(self):
        signals = normalize_radon(RADON_CC_INPUT)
        assert not any(s.rule_id.endswith("ok") for s in signals)

    def test_mi_rank_f_emits_signal(self):
        signals = normalize_radon(RADON_MI_INPUT)
        # Only "src/big.py" (rank F) emits; "src/ok.py" (rank A) does not.
        assert len(signals) == 1
        s = signals[0]
        assert s.file_path == "src/big.py"
        assert s.severity == "medium"
        assert s.confidence == pytest.approx(0.90)
        assert s.meta.get("mi") == 42.5

    def test_mixed_cc_and_mi_input(self):
        combined = dict(RADON_CC_INPUT)
        combined.update(RADON_MI_INPUT)
        signals = normalize_radon(combined)
        # CC: foo (E) + bar (D) + MI: big (F) = 3
        assert len(signals) == 3


# ---------------------------------------------------------------------------
# Frozen dataclass invariant
# ---------------------------------------------------------------------------


class TestRawSignalFrozen:
    def test_raw_signal_is_immutable(self):
        signals = normalize_semgrep(SEMGREP_INPUT)
        s = signals[0]
        for field in ("tool", "rule_id", "category", "severity"):
            with pytest.raises(Exception):
                setattr(s, field, "hacked")
