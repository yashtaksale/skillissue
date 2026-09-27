"""Output guards for LLM findings (T-4.4).

Validates and filters findings returned by the LLM against:
  - Pydantic schema (via FindingOutput)
  - Signal ID references real signals
  - File path exists in source
  - Line range overlaps source lines
  - No URLs or HTML in explanation/fix
  - Roast blocklist filtering
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from typing import Any

from skillissue.pipeline.llm.schema import FindingOutput

# Patterns to strip from free-text fields
_URL_RE = re.compile(r"https?://\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&[a-zA-Z]+;")

# Roast blocklist — phrases the LLM should never emit
ROAST_BLOCKLIST: list[str] = [
    "you should have used",
    "any competent developer",
    "obviously",
    "trivially",
    "how hard is it to",
    "i can't believe",
    "this is why we can't have nice things",
]

MAX_SNIPPET_LENGTH = 5_000
MAX_EXPLANATION_LENGTH = 2_000
MAX_FIX_LENGTH = 2_000


@dataclass
class GuardResult:
    """Result of validating one finding."""

    finding: FindingOutput | None = None  # None if dropped
    dropped: bool = False
    drop_reason: str = ""
    fields_modified: list[str] = field(default_factory=list)


@dataclass
class GuardStats:
    """Aggregate guard statistics."""

    total_input: int = 0
    total_output: int = 0
    total_dropped: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    fields_modified: dict[str, int] = field(default_factory=dict)
    injection_suspected: bool = False

    def record_drop(self, reason: str) -> None:
        self.total_dropped += 1
        self.drop_reasons[reason] = self.drop_reasons.get(reason, 0) + 1

    def record_modification(self, field: str) -> None:
        self.fields_modified[field] = self.fields_modified.get(field, 0) + 1


# ── Main guard function ──────────────────────────────────────────────


def apply_guards(
    raw_findings: list[dict],
    *,
    valid_signal_ids: set[str],
    source_files: dict[str, int] | None = None,
    roast_blocklist: list[str] | None = None,
) -> tuple[list[FindingOutput], GuardStats]:
    """Validate and sanitize a batch of raw LLM findings.

    Args:
        raw_findings: List of dicts from LLM tool_use output.
        valid_signal_ids: Set of signal IDs the LLM was told about.
        source_files: Optional ``{file_path: line_count}`` for line-range checks.
        roast_blocklist: Override default blocklist.

    Returns:
        (validated_findings, stats)
    """
    stats = GuardStats()
    stats.total_input = len(raw_findings)
    blocklist = roast_blocklist or ROAST_BLOCKLIST
    valid: list[FindingOutput] = []

    for raw in raw_findings:
        result = _guard_single(
            raw,
            valid_signal_ids=valid_signal_ids,
            source_files=source_files or {},
            blocklist=blocklist,
        )
        if result.finding is not None:
            valid.append(result.finding)
            stats.total_output += 1
        else:
            stats.record_drop(result.drop_reason)
        for f in result.fields_modified:
            stats.record_modification(f)

    return valid, stats


# ── Per-finding guard ────────────────────────────────────────────────


def _guard_single(
    raw: dict,
    *,
    valid_signal_ids: set[str],
    source_files: dict[str, int],
    blocklist: list[str],
) -> GuardResult:
    """Validate and sanitize a single raw finding dict."""
    result = GuardResult()

    # Schema validation via Pydantic
    try:
        finding = FindingOutput(**raw)
    except Exception:
        return GuardResult(dropped=True, drop_reason="schema_error")

    # 2. Signal ID must reference a real signal
    if finding.signal_id not in valid_signal_ids:
        result = GuardResult(dropped=True, drop_reason="invalid_signal_id")
        return result

    # 3. Line range sanity
    file_lines = source_files.get(finding.file_path, 0)
    if file_lines and finding.line_start > file_lines:
        return GuardResult(dropped=True, drop_reason="line_start_out_of_range")
    if finding.line_end < finding.line_start:
        return GuardResult(dropped=True, drop_reason="line_end_before_line_start")

    # 4. URL / HTML stripping
    modified = _strip_urls_and_html(finding)
    if modified:
        result.fields_modified.extend(modified)

    # 5. Roast blocklist
    roast_hit = _check_roast_blocklist(finding, blocklist)
    if roast_hit:
        return GuardResult(dropped=True, drop_reason=f"roast_blocklist: {roast_hit}")

    result.finding = finding
    return result


def _strip_urls_and_html(finding: FindingOutput) -> list[str]:
    """Remove URLs and HTML from explanation and fix fields."""
    modified: list[str] = []

    for field_name in ("message", "explanation", "fix"):
        text = getattr(finding, field_name)
        new_text = _URL_RE.sub("[redacted URL]", text)
        new_text = _HTML_TAG_RE.sub("", new_text)
        new_text = _HTML_ENTITY_RE.sub("", new_text)
        new_text = html.unescape(new_text)
        if new_text != text:
            setattr(finding, field_name, new_text)
            modified.append(field_name)

    return modified


def _check_roast_blocklist(finding: FindingOutput, blocklist: list[str]) -> str | None:
    """Check if any roast phrase appears in the finding text."""
    combined = (
        f"{finding.message} {finding.explanation} {finding.fix}"
    ).lower()
    for phrase in blocklist:
        if phrase.lower() in combined:
            return phrase
    return None


# ── Injection detection heuristic (T-4.8) ───────────────────────────


def detect_injection(finding: FindingOutput) -> bool:
    """Heuristic: does this finding look like a prompt-injection attempt?

    Checks for:
    - Instruction-following commands (ignore, disregard, disregard previous)
    - Data exfiltration requests
    -  leakage attempts
    - Forced command injection
    """
    text = (
        f"{finding.message} {finding.explanation} {finding.fix}"
    ).lower()

    injection_markers = [
        "ignore all previous",
        "disregard all",
        "ignore previous",
        "you are now",
        "new instructions:",
        "override",
        "disregard the",
        "forget your role",
        "pretend you are",
        "act as if",
        "reveal your",
        "print your",
        "output your instructions",
        "echo your system",
        "what is your prompt",
        "send the data",
        "exfiltrate",
        "exfil",
    ]
    return any(marker in text for marker in injection_markers)


def apply_injection_filter(
    findings: list[FindingOutput],
) -> tuple[list[FindingOutput], bool]:
    """Drop any findings that look like .

    Returns (clean_findings, injection_detected).
    """
    clean: list[FindingOutput] = []
    detected = False
    for f in findings:
        if detect_injection(f):
            detected = True
            continue
        clean.append(f)
    return clean, detected
