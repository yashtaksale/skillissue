"""Signal normalizer: convert raw tool signals to common format."""
from __future__ import annotations

from typing import Any


def normalize_signals(raw_signals: list[dict]) -> list[dict]:
    """Normalize raw signals from all tools into a consistent format.

    Each normalized signal has:
      - signal_id: unique identifier
      - tool: source tool name
      - rule_id: tool-specific rule identifier
      - category: security | bugs | maintainability | performance | hygiene
      - severity: critical | high | medium | low
      - confidence: 0.0-1.0
      - file_path: repo-relative path
      - line_start: first affected line (1-indexed)
      - line_end: last affected line
      - message: human-readable description
      - snippet: code context (may be empty)
    """
    normalized: list[dict] = []
    seen: set[tuple[str, str, int]] = set()

    for i, sig in enumerate(raw_signals):
        if not isinstance(sig, dict):
            continue

        # Validate required fields
        tool = sig.get("tool", "unknown")
        rule_id = sig.get("rule_id", "unknown")
        file_path = _normalize_path(sig.get("file_path", ""))
        line_start = max(1, int(sig.get("line_start", 1)))

        # Dedup by (file, rule, line)
        key = (file_path, rule_id, line_start)
        if key in seen:
            continue
        seen.add(key)

        # Validate severity
        severity = sig.get("severity", "medium")
        if severity not in ("critical", "high", "medium", "low"):
            severity = "medium"

        # Validate category
        category = sig.get("category", "maintainability")
        if category not in ("security", "bugs", "maintainability", "performance", "hygiene"):
            category = "maintainability"

        # Validate confidence
        confidence = float(sig.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        normalized.append({
            "signal_id": f"{tool}:{rule_id}:{i}",
            "tool": tool,
            "rule_id": rule_id,
            "category": category,
            "severity": severity,
            "confidence": round(confidence, 2),
            "file_path": file_path,
            "line_start": line_start,
            "line_end": max(line_start, int(sig.get("line_end", line_start))),
            "message": str(sig.get("message", ""))[:500],
            "snippet": str(sig.get("snippet", ""))[:500],
        })

    return normalized


def _normalize_path(path: str) -> str:
    """Normalize file path separators."""
    return path.replace("\\", "/").lstrip("/")
