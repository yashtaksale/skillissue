"""Severity and confidence mapping per tool (ARCHITECTURE.md §7.4).

Every scanner emits its own severity vocabulary.  This module converts
(raw_tool_severity) → (category, severity, confidence) so the rest of the
pipeline only sees one canonical scale.

Rules are implemented as a lookup table; unmatched severities fall back to
(``"maintainability"``, ``"low"``, ``0.50``).
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# (tool, raw_severity) → (category, severity, confidence)
# All keys are normalised to lowercase for case-insensitive lookup.
# ---------------------------------------------------------------------------
_MAP: dict[tuple[str, str], tuple[str, str, float]] = {
    # -- Semgrep ------------------------------------------------------------
    ("semgrep", "error"):   ("security",        "high",   0.85),
    ("semgrep", "warning"): ("security",        "medium", 0.70),
    ("semgrep", "info"):    ("maintainability", "low",    0.55),
    # -- Bandit -------------------------------------------------------------
    ("bandit", "high"):     ("security", "high",   0.85),
    ("bandit", "medium"):   ("security", "medium", 0.70),
    ("bandit", "low"):      ("security", "low",    0.55),
    # -- ESLint security/* rules --------------------------------------------
    # Default confidence is 0.65; noisy rules get reduced to 0.45 below.
    ("eslint", "medium"):   ("security", "medium", 0.65),
    ("eslint", "high"):     ("security", "high",   0.65),
    ("eslint", "low"):      ("security", "low",    0.65),
    ("eslint", "warning"):  ("security", "medium", 0.65),
    ("eslint", "error"):    ("security", "high",   0.65),
    # -- gitleaks -----------------------------------------------------------
    # Provider-specific rules get critical/0.95; generic rules get high/0.70.
    ("gitleaks", "provider-specific"): ("security", "critical", 0.95),
    ("gitleaks", "generic"):           ("security", "high",      0.70),
    # -- Lizard -------------------------------------------------------------
    # (handled in map_severity via rule_id prefix; table entries are fallbacks)
    ("lizard", "medium"):   ("maintainability", "medium", 0.95),
    ("lizard", "low"):      ("maintainability", "low",    0.95),
    # -- Radon --------------------------------------------------------------
    ("radon", "high"):      ("maintainability", "medium", 0.90),
    ("radon", "low"):       ("maintainability", "low",    0.90),
}

# Fallback when a (tool, severity) pair is not in _MAP.
_DEFAULT_CATEGORY = "maintainability"
_DEFAULT_SEVERITY = "low"
_DEFAULT_CONFIDENCE = 0.50

# ESLint noisy rules that get lower confidence (0.45 instead of 0.65).
_ESLINT_NOISY_RULES: set[str] = {
    "detect-object-injection",
    "no-useless-catch",
    "no-useless-escape",
    "prefer-object-spread",
}


def map_severity(
    tool: str,
    raw_severity: str,
    rule_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> tuple[str, str, float]:
    """Map a raw tool severity to (category, severity, confidence).

    Args:
        tool: Scanner tool name (case-insensitive).
        raw_severity: The raw severity string from the tool (case-insensitive).
        rule_id: Optional rule identifier used for ESLint noisy-rule detection.
        meta: Optional extra metadata dict; may contain ``ruleId``.

    Returns:
        A 3-tuple ``(category, severity, confidence)``.
    """
    normalised_tool = tool.lower()

    # Lizard: confidence and severity depend on rule_id prefix, not raw_severity.
    #   ccn_*     → ("maintainability", "medium", 0.95) — CCN thresholds
    #   length_*  → ("maintainability", "low",    0.90) — length thresholds
    if normalised_tool == "lizard":
        rule = rule_id or ""
        if rule.startswith("ccn_"):
            return "maintainability", "medium", 0.95
        if rule.startswith("length_"):
            return "maintainability", "low", 0.90

    key = (normalised_tool, raw_severity.strip().lower())

    # ESLint special-case: adjust confidence based on whether the rule is
    # known-noisy (ARCHITECTURE.md §7.4: 0.45 for noisy, 0.65 otherwise).
    if normalised_tool == "eslint" and key in _MAP:
        category, severity, confidence = _MAP[key]
        effective_rule_id = rule_id or (meta or {}).get("ruleId", "")
        # Strip namespace prefix (e.g. "security/detect-object-injection" -> "detect-object-injection").
        rule_name = effective_rule_id.split("/")[-1] if effective_rule_id else ""
        if rule_name in _ESLINT_NOISY_RULES:
            confidence = 0.45
        return category, severity, confidence

    if key in _MAP:
        return _MAP[key]

    return _DEFAULT_CATEGORY, _DEFAULT_SEVERITY, _DEFAULT_CONFIDENCE
