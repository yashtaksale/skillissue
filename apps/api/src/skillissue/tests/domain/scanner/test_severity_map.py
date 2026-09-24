"""Table-driven tests for the severity/confidence map (ARCHITECTURE.md §7.4)."""
from __future__ import annotations

import pytest

from skillissue.domain.scanner.severity_map import map_severity


# ---------------------------------------------------------------------------
# (tool, raw_severity, rule_id?, meta?) → (category, severity, confidence)
# ---------------------------------------------------------------------------
SEVERITY_CASES = [
    # -- Semgrep --
    ("semgrep", "ERROR",   None, None, "security",     "high",   0.85),
    ("semgrep", "WARNING", None, None, "security",     "medium", 0.70),
    ("semgrep", "INFO",    None, None, "maintainability", "low", 0.55),
    # -- Bandit --
    ("bandit", "HIGH",   None, None, "security", "high",   0.85),
    ("bandit", "MEDIUM", None, None, "security", "medium", 0.70),
    ("bandit", "LOW",    None, None, "security", "low",    0.55),
    # -- ESLint noisy rule gets 0.45 confidence --
    (
        "eslint", "error", "detect-object-injection", None,
        "security", "high", 0.45,
    ),
    (
        "eslint", "warning", "detect-object-injection", None,
        "security", "medium", 0.45,
    ),
    # -- ESLint non-noisy rule gets 0.65 confidence --
    (
        "eslint", "error", "no-eval", None,
        "security", "high", 0.65,
    ),
    (
        "eslint", "warning", "no-eval", None,
        "security", "medium", 0.65,
    ),
    # ESLint meta-supplied ruleId path
    (
        "eslint", "warning", None, {"ruleId": "prefer-object-spread"},
        "security", "medium", 0.45,
    ),
    (
        "eslint", "warning", None, {"ruleId": "no-implicit-any"},
        "security", "medium", 0.65,
    ),
    # -- gitleaks --
    (
        "gitleaks", "provider-specific", None, None,
        "security", "critical", 0.95,
    ),
    (
        "gitleaks", "generic", None, None,
        "security", "high", 0.70,
    ),
    # -- Lizard (via rule_id prefix) --
    ("lizard", "high", "ccn_process", None,
     "maintainability", "medium", 0.95),
    ("lizard", "low", "ccn_helper", None,
     "maintainability", "medium", 0.95),
    ("lizard", "high", "length_handler", None,
     "maintainability", "low", 0.90),
    ("lizard", "low", "length_helper", None,
     "maintainability", "low", 0.90),
    # -- Radon --
    ("radon", "high", None, None,
     "maintainability", "medium", 0.90),
    ("radon", "low", None, None,
     "maintainability", "low", 0.90),
]


class TestMapSeverity:
    """Each (tool, raw_severity) combo produces the expected mapping."""

    @pytest.mark.parametrize(
        "tool,raw_severity,rule_id,meta,expected_cat,expected_sev,expected_conf",
        SEVERITY_CASES,
        ids=[f"{c[0]}/{c[1]}" for c in SEVERITY_CASES],
    )
    def test_map_severity(
        self,
        tool: str,
        raw_severity: str,
        rule_id: str | None,
        meta: dict | None,
        expected_cat: str,
        expected_sev: str,
        expected_conf: float,
    ) -> None:
        category, severity, confidence = map_severity(
            tool, raw_severity, rule_id=rule_id, meta=meta
        )
        assert category == expected_cat
        assert severity == expected_sev
        assert confidence == pytest.approx(expected_conf)

    def test_unknown_tool_returns_defaults(self) -> None:
        category, severity, confidence = map_severity("nope", "CRITICAL")
        assert category == "maintainability"
        assert severity == "low"
        assert confidence == pytest.approx(0.50)

    def test_case_insensitive_tool(self) -> None:
        category, severity, confidence = map_severity("SEMGREP", "error")
        assert severity == "high"
        assert confidence == pytest.approx(0.85)

    def test_case_insensitive_severity(self) -> None:
        category, severity, confidence = map_severity("bandit", "high")
        assert severity == "high"
        assert confidence == pytest.approx(0.85)

    def test_eslint_rule_name_with_namespace(self) -> None:
        """Namespaced rule id `security/detect-object-injection` -> noisy."""
        category, severity, confidence = map_severity(
            "eslint", "warning", rule_id="security/detect-object-injection"
        )
        assert confidence == pytest.approx(0.45)
