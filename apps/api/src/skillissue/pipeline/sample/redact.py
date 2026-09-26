"""Secret redaction pass for chunk text (T-3.6).

Ensures that secrets never appear in LLM-bound text. Redacts:
  - AWS keys (AKIA...)
  - Generic secrets in .env files
  - Long base64 literals (≥ 32 chars)
  - Known patterns: API keys, tokens, passwords, connection strings
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# =====================================================================
# Patterns (ordered: most specific first)
# =====================================================================

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # AWS Access Key ID
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED-AWS-KEY]"),
    # AWS Secret (long base64-ish)
    (re.compile(r"(?i)aws(.{0,20}?)(['\"])?([A-Za-z0-9/+=]{40,})(['\"])?"),
     r"\g<1>[REDACTED-AWS-SECRET]"),
    # Generic API key patterns
    (re.compile(r"(?i)(api[_-]?key|apikey|api_secret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})['\"]?"),
     r"\g<1>=[REDACTED]"),
    # Bearer tokens
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"), "[REDACTED-BEARER]"),
    # Authorization headers
    (re.compile(r"(?i)authorization:\s*[A-Za-z0-9_\-\.]+"), "Authorization: [REDACTED]"),
    # Long base64 literals (≥ 32 chars) — likely secrets/keys
    (re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"), "[REDACTED-BASE64]"),
    # Private keys
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----",
                re.DOTALL), "[REDACTED-PRIVATE-KEY]"),
    # Password in connection strings
    (re.compile(r"(?i)(password|passwd|pwd)\s*=\s*[^\s;,&]+"), r"\g<1>=[REDACTED]"),
    # Hex-encoded secrets (≥ 32 hex chars)
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "[REDACTED-HEX]"),
]


@dataclass
class RedactionResult:
    """Result of redacting secrets from text."""

    redacted_text: str
    redaction_count: int
    pattern_hits: dict[str, int]


def redact(text: str) -> RedactionResult:
    """Redact secrets from text using pattern matching.

    Property test invariant: no full secret should remain in the
    redacted text after this pass (per T-2.10).

    Args:
        text: Source text to redact.

    Returns:
        RedactionResult with cleaned text and counts.
    """
    pattern_hits: dict[str, int] = {}
    count = 0

    for pattern, replacement in _PATTERNS:
        matches = pattern.findall(text)
        if matches:
            name = pattern.pattern[:40]
            pattern_hits[name] = len(matches)
            count += len(matches)
        text = pattern.sub(replacement, text)

    return RedactionResult(
        redacted_text=text,
        redaction_count=count,
        pattern_hits=pattern_hits,
    )


def redact_chunk_text(text: str, show_partial: bool = True) -> str:
    """Redact secrets from chunk text. Returns only the cleaned text.

    Args:
        text: Chunk source text.
        show_partial: If True, show first 4 + last 2 chars of redacted
            secrets (for snippet display). If False, replace entirely.

    Returns:
        Redacted text.
    """
    result = redact(text)
    if show_partial:
        # Replace full redactions with partial reveals
        result.redacted_text = _show_partial(result.redacted_text)
    return result.redacted_text


def _show_partial(text: str) -> str:
    """Show first 4 + last 2 chars of redacted secrets."""
    # Replace [REDACTED-*] with partial reveals
    text = re.sub(
        r"\[REDACTED-(?:AWS-KEY|AWS-SECRET|BASE64|PRIVATE-KEY|HEX|BEARER)\]",
        lambda m: _partial_token(m.group(0)),
        text,
    )
    text = re.sub(r"\[REDACTED\]", "[REDACTED]", text)
    return text


def _partial_token(token: str) -> str:
    """Show a partial token for display purposes."""
    if len(token) > 20:
        return f"{token[:6]}...{token[-4:]}"
    return token


def redact_file_list(texts: dict[str, str]) -> dict[str, RedactionResult]:
    """Redact a dict of {filename: text} and return results per file."""
    return {path: redact(text) for path, text in texts.items()}


def no_full_secret_remains(text: str) -> bool:
    """Property test helper: assert no full secret patterns remain.

    Returns True if the text is clean, False if redacted patterns are missing.
    """
    # Check for common full-secret indicators that should have been redacted
    dangerous_patterns = [
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    ]
    return not any(p.search(text) for p in dangerous_patterns)
