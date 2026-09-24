"""Immutable raw signal produced by scanner tools before normalization."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawSignal:
    """Canonical representation of a single finding from a scanner tool.

    This is the standardised intermediate format every tool normalises into.
    It is immutable so downstream stages can safely share references.
    """

    signal_id: str        # unique within a scan run (e.g. "sig_000001")
    tool: str             # emitting tool name: semgrep | bandit | eslint |
                          # gitleaks | lizard | radon
    rule_id: str          # tool-specific rule identifier
    category: str         # security | bugs | performance | maintainability
    severity: str         # critical | high | medium | low
    confidence: float     # 0.0 – 1.0
    file_path: str        # repo-relative path
    line_start: int
    line_end: int
    message: str          # human-readable description
    snippet: str          # source text (masked if it contains secrets)
    meta: dict            # tool-specific extra data (CWE, OWASP, …)
