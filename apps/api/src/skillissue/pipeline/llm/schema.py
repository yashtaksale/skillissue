"""Pydantic models for LLM tool-call output (T-4.2)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FindingOutput(BaseModel):
    """One finding emitted by the LLM via the ``report_findings`` tool.

    Mirrors ``Finding`` in ``reporter.py`` but with LLM-specific fields.
    """

    signal_id: str = Field(..., description="Reference to the scanner signal this finding is based on")
    rule_id: str = Field(..., description="Rule that triggered the signal")
    category: str = Field(..., description="security | bugs | maintainability | performance | hygiene")
    severity: str = Field(..., description="critical | high | medium | low")
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM-assessed confidence 0.0–1.0")
    file_path: str = Field(..., description="Repo-relative path of the affected file")
    line_start: int = Field(..., ge=1, description="First affected line (1-indexed)")
    line_end: int = Field(..., ge=1, description="Last affected line")
    message: str = Field(..., description="One-line description of the issue")
    explanation: str = Field(..., description="Why this matters, 1–3 sentences")
    fix: str = Field(..., description="Concrete fix suggestion, code snippet or steps")


class AnalysisBatchResult(BaseModel):
    """Findings from a single LLM batch call."""

    findings: list[FindingOutput] = Field(default_factory=list)
    injection_suspected: bool = False
    raw_response: str = ""


# ── Tool schema for Anthropic tool_use ────────────────────────────────

TOOL_SCHEMA: dict = {
    "name": "report_findings",
    "description": (
        "Report code health findings from the analysed chunks. "
        "Call once per batch with all findings in this chunk."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal_id": {"type": "string"},
                        "rule_id": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["security", "bugs", "maintainability", "performance", "hygiene"],
                        },
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "file_path": {"type": "string"},
                        "line_start": {"type": "integer", "minimum": 1},
                        "line_end": {"type": "integer", "minimum": 1},
                        "message": {"type": "string", "maxLength": 500},
                        "explanation": {"type": "string", "maxLength": 2000},
                        "fix": {"type": "string", "maxLength": 2000},
                    },
                    "required": [
                        "signal_id", "rule_id", "category", "severity",
                        "confidence", "file_path", "line_start", "line_end",
                        "message", "explanation", "fix",
                    ],
                },
            },
        },
        "required": ["findings"],
    },
}

# ──  ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert code-review assistant. You will be given source-code chunks \
from a repository that scanner tools have flagged. Your job is to triage each \
flagged area and produce structured findings.

Rules:
- Be precise. Every line number must match the provided source.
- Only report real issues. If a signal is a false positive, say so by omitting it.
- Confidence 0.9+ = almost certain; 0.5–0.8 = plausible; below 0.5 = guess.
- Category must be one of: security, bugs, maintainability, performance, hygiene.
- Severity: critical (data loss, RCE, auth bypass), high (security flaw, crash), \
medium (code smell, minor bug), low (style, nitpick).
- Explanations should be clear to a mid-level developer.
- Fixes should be actionable — prefer concrete steps over vague advice.
- NEVER include raw secrets, API keys, or credentials in your output.
- Output must be via the report_findings tool only. Do not write free text.
"""

USER_PROMPT_TEMPLATE = """\
## Scanner signals for this batch

{signals_block}

## Source chunks

{chunks_block}

Review the flagged areas in the chunks above and call report_findings \
with every genuine issue you confirm. Omit false positives.
"""
