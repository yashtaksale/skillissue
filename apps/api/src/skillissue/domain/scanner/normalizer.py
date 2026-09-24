"""Tool output normalizers — convert each scanner's raw JSON into ``RawSignal``s.

Each ``normalize_*`` function accepts the parsed JSON from its respective
tool, applies the severity/confidence map, masks any secrets in the snippet,
and returns a list of immutable ``RawSignal`` objects.
"""
from __future__ import annotations

from typing import Any

from skillissue.domain.scanner.masker import mask_secret
from skillissue.domain.scanner.models import RawSignal
from skillissue.domain.scanner.severity_map import map_severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source_lines(file_path: str) -> list[str]:
    """Best-effort read of a source file's lines."""
    try:
        import pathlib
        p = pathlib.Path(file_path)
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        pass
    return []


def _build_snippet(file_path: str, line_start: int, line_end: int, raw_snippet: str = "") -> str:
    """Return a masked snippet for the given file and line range."""
    if raw_snippet.strip():
        # Tool already gave us the line(s); mask them and return.
        return mask_secret(raw_snippet)

    lines = _read_source_lines(file_path)
    if not lines:
        return ""

    start = max(0, line_start - 1)
    end = min(len(lines), max(line_start, line_end))
    selected = lines[start:end]
    return "\n".join(f"{i + line_start}│{line}" for i, line in enumerate(selected))


def _emit(
    tool: str,
    rule_id: str,
    raw_severity: str,
    file_path: str,
    line_start: int,
    line_end: int,
    message: str,
    raw_snippet: str = "",
    meta: dict[str, Any] | None = None,
) -> RawSignal:
    """Build a single ``RawSignal``, applying the severity map and masking."""
    category, severity, confidence = map_severity(
        tool, raw_severity, rule_id=rule_id, meta=meta or {}
    )
    snippet = mask_secret(raw_snippet) if raw_snippet else _build_snippet(
        file_path, line_start, line_end
    )
    signal_id = f"{tool}_{rule_id}_{line_start}"
    return RawSignal(
        signal_id=signal_id,
        tool=tool,
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=confidence,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        message=message,
        snippet=snippet,
        meta=meta or {},
    )


# ---------------------------------------------------------------------------
# Semgrep
# ---------------------------------------------------------------------------
# Semgrep JSON: {"results": [...], "errors": [...]}
# Each result:
#   {
#     "check_id": "python.lang.security.audit.dangerous-system-call",
#     "path": "app/main.py",
#     "start": {"line": 1, "col": 1},
#     "end":   {"line": 3, "col": 1},
#     "extra": {
#       "severity": "ERROR",
#       "metadata": {"category": "security", "cwe": [...], "owasp": [...]},
#       "message": "Use of exec()...",
#       "lines": "exec(user_input)\n"
#     }
#   }


def normalize_semgrep(output: dict[str, Any]) -> list[RawSignal]:
    """Convert Semgrep JSON output to ``RawSignal`` list."""
    signals: list[RawSignal] = []
    results = output.get("results", [])
    for r in results:
        check_id = r.get("check_id", "unknown")
        path = r.get("path", "")
        start = r.get("start", {})
        end = r.get("end", {})
        extra = r.get("extra", {})
        raw_severity = extra.get("severity", "INFO")
        message = extra.get("message", "")
        raw_lines = extra.get("lines", "")
        meta = extra.get("metadata", {}) or {}
        # flatten cwe / owasp into meta
        if "cwe" in meta:
            meta.setdefault("cwe", [])
        if "owasp" in meta:
            meta.setdefault("owasp", [])

        signals.append(
            _emit(
                tool="semgrep",
                rule_id=check_id,
                raw_severity=raw_severity,
                file_path=path,
                line_start=start.get("line", 0),
                line_end=end.get("line", start.get("line", 0)),
                message=message,
                raw_snippet=raw_lines,
                meta=meta,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# Bandit
# ---------------------------------------------------------------------------
# Bandit JSON: {"results": [...], "errors": [...]}
# Each result:
#   {
#     "issue_text": "Use of exec...",
#     "issue_severity": "HIGH",
#     "issue_confidence": "HIGH",
#     "test_name": "exec_used",
#     "test_id": "B102",
#     "filename": "app/main.py",
#     "line_range": [1, 3],
#     "code": "exec(x)\n"
#   }


def normalize_bandit(output: dict[str, Any]) -> list[RawSignal]:
    """Convert Bandit JSON output to ``RawSignal`` list."""
    signals: list[RawSignal] = []
    results = output.get("results", [])
    for r in results:
        test_id = r.get("test_id", "B???")
        filename = r.get("filename", "")
        line_range = r.get("line_range", [])
        line_start = line_range[0] if line_range else 0
        line_end = line_range[-1] if line_range else line_start
        raw_severity = r.get("issue_severity", "LOW")
        message = r.get("issue_text", "")
        code = r.get("code", "")
        meta = {
            "test_name": r.get("test_name", ""),
            "issue_confidence": r.get("issue_confidence", ""),
        }

        signals.append(
            _emit(
                tool="bandit",
                rule_id=test_id,
                raw_severity=raw_severity,
                file_path=filename,
                line_start=line_start,
                line_end=line_end,
                message=message,
                raw_snippet=code,
                meta=meta,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# ESLint
# ---------------------------------------------------------------------------
# ESLint JSON (flat-config, formatter=json):
# [
#   {
#     "filePath": "src/app.ts",
#     "messages": [
#       {
#         "ruleId": "@typescript-eslint/no-explicit-any",
#         "severity": 2,         // 1=warning, 2=error
#         "message": "Unexpected any...",
#         "line": 1,
#         "endLine": 1,
#         "column": 1,
#         "endColumn": 10,
#         "nodeType": "TSAnyKeyword",
#         "source": "  const x: any = 1;"
#       }
#     ]
#   }
# ]


_SEVERITY_MAP_ESLINT = {1: "warning", 2: "error"}


def normalize_eslint(output: list[dict[str, Any]]) -> list[RawSignal]:
    """Convert ESLint JSON output to ``RawSignal`` list."""
    signals: list[RawSignal] = []
    for file_entry in output:
        file_path = file_entry.get("filePath", "")
        for msg in file_entry.get("messages", []):
            rule_id = msg.get("ruleId", "unknown")
            sev_level = msg.get("severity", 1)
            raw_severity = _SEVERITY_MAP_ESLINT.get(sev_level, "warning")
            line_start = msg.get("line", 0)
            line_end = msg.get("endLine", line_start)
            message = msg.get("message", "")
            source = msg.get("source", "")
            meta = {
                "nodeType": msg.get("nodeType", ""),
                "column": msg.get("column"),
                "endColumn": msg.get("endColumn"),
            }

            signals.append(
                _emit(
                    tool="eslint",
                    rule_id=rule_id,
                    raw_severity=raw_severity,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    message=message,
                    raw_snippet=source,
                    meta=meta,
                )
            )
    return signals


# ---------------------------------------------------------------------------
# gitleaks
# ---------------------------------------------------------------------------
# gitleaks JSON (--report-format json):
# [
#   {
#     "Description": "AWS Access Key",
#     "Rule": "AWS",
#     "Secret": "AKIAIOSFODNN7EXAMPLE",
#     "File": "config/credentials",
#     "Line": 42,
#     "Column": 1,
#     "StartColumn": 5,
#     "EndColumn": 29,
#     "Commit": "abc123"
#   }
# ]

# Provider rules that receive critical/0.95; everything else is generic.
_GITLEAKS_PROVIDER_RULES: set[str] = {
    "AWS", "GitHub", "Stripe", "Slack", "Google", "SlackWebhook",
    "Twilio", "Mailchimp", "Paypal", "Square", "Heroku", "Docker",
    "Npm", "Artifactory", "Jfrog", "Azure", "SendGrid", "Mailgun",
    "DigitalOcean", "Datadog", "NewRelic", "Databricks", "Pivotal",
    "Linkedin", "Facebook", "Twitter", "Asana", "Bitbucket",
}


def normalize_gitleaks(output: list[dict[str, Any]]) -> list[RawSignal]:
    """Convert gitleaks JSON output to ``RawSignal`` list."""
    signals: list[RawSignal] = []
    for entry in output:
        rule = entry.get("Rule", "generic")
        raw_severity = (
            "provider-specific" if rule in _GITLEAKS_PROVIDER_RULES else "generic"
        )
        file_path = entry.get("File", "")
        line = entry.get("Line", 0)
        message = entry.get("Description", f"gitleaks: {rule}")
        secret = entry.get("Secret", "")
        meta = {
            "rule": rule,
            "start_column": entry.get("StartColumn"),
            "end_column": entry.get("EndColumn"),
            "commit": entry.get("Commit", ""),
            "secret_masked": mask_secret(secret) if secret else "",
        }

        signals.append(
            _emit(
                tool="gitleaks",
                rule_id=rule,
                raw_severity=raw_severity,
                file_path=file_path,
                line_start=line,
                line_end=line,
                message=message,
                raw_snippet="",
                meta=meta,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# Lizard
# ---------------------------------------------------------------------------
# Lizard JSON (Python API: lizard.analyze_files → dict):
# {
#   "average_complexity": 3.2,
#   "files": [
#     {
#       "filename": "src/app.py",
#       "file_complexity": 5,
#       "functions": [
#         {
#           "name": "process",
#           "complexity": 15,
#           "start_line": 10,
#           "end_line": 50,
#           "length": 40,
#           "parameters": 2
#         }
#       ]
#     }
#   ]
# }


def normalize_lizard(output: dict[str, Any]) -> list[RawSignal]:
    """Convert Lizard analysis output to ``RawSignal`` list.

    Emits one signal per function whose CCN exceeds thresholds:
    - CCN > 30  → medium severity / 0.95 confidence
    - CCN > 15  → low severity / 0.95 confidence
    Functions with length > 200 / > 100 also get low-severity maintainability
    signals (confidence 0.90).
    """
    signals: list[RawSignal] = []
    files = output.get("files", [])
    for file_entry in files:
        file_path = file_entry.get("filename", "")
        for func in file_entry.get("functions", []):
            ccn = func.get("complexity", 0)
            length = func.get("length", 0)
            start_line = func.get("start_line", 0)
            end_line = func.get("end_line", start_line)
            func_name = func.get("name", "unknown")

            # CCN threshold signals.
            if ccn > 30:
                signals.append(
                    _emit(
                        tool="lizard",
                        rule_id=f"ccn_{func_name}",
                        raw_severity="high",
                        file_path=file_path,
                        line_start=start_line,
                        line_end=end_line,
                        message=(
                            f"Function '{func_name}' has CCN {ccn} (>30)"
                        ),
                        meta={"ccn": ccn, "function": func_name},
                    )
                )
            elif ccn > 15:
                signals.append(
                    _emit(
                        tool="lizard",
                        rule_id=f"ccn_{func_name}",
                        raw_severity="low",
                        file_path=file_path,
                        line_start=start_line,
                        line_end=end_line,
                        message=(
                            f"Function '{func_name}' has CCN {ccn} (>15)"
                        ),
                        meta={"ccn": ccn, "function": func_name},
                    )
                )

            # Length threshold signals.
            if length > 200:
                signals.append(
                    _emit(
                        tool="lizard",
                        rule_id=f"length_{func_name}",
                        raw_severity="low",
                        file_path=file_path,
                        line_start=start_line,
                        line_end=end_line,
                        message=(
                            f"Function '{func_name}' is {length} lines long (>200)"
                        ),
                        meta={"length": length, "function": func_name},
                    )
                )
            elif length > 100:
                signals.append(
                    _emit(
                        tool="lizard",
                        rule_id=f"length_{func_name}",
                        raw_severity="low",
                        file_path=file_path,
                        line_start=start_line,
                        line_end=end_line,
                        message=(
                            f"Function '{func_name}' is {length} lines long (>100)"
                        ),
                        meta={"length": length, "function": func_name},
                    )
                )
    return signals


# ---------------------------------------------------------------------------
# Radon
# ---------------------------------------------------------------------------
# Radon CC JSON: {"path/to/file.py": [{"name": "foo", "type": "function",
#                                       "complexity": 35, "rank": "E",
#                                       "line": 1, "endline": 20}]}
#
# Radon MI JSON:  {"path/to/file.py": {"mi": 42.5, "rank": "C",
#                                       "methods": [...]}}


def normalize_radon(output: dict[str, Any]) -> list[RawSignal]:
    """Convert Radon complexity / maintainability-index output to ``RawSignal``s."""
    signals: list[RawSignal] = []
    for file_path, blocks in output.items():
        # Handle both CC output (list of dicts) and MI output (dict).
        if isinstance(blocks, dict):
            # MI-style: single entry per file.
            rank = blocks.get("rank", "C")
            if rank in ("E", "F"):
                signals.append(
                    _emit(
                        tool="radon",
                        rule_id="mi_rank",
                        raw_severity="high",
                        file_path=file_path,
                        line_start=1,
                        line_end=1,
                        message=f"Maintainability index rank {rank}",
                        meta={"rank": rank, "mi": blocks.get("mi")},
                    )
                )
            elif rank == "D":
                signals.append(
                    _emit(
                        tool="radon",
                        rule_id="mi_rank",
                        raw_severity="low",
                        file_path=file_path,
                        line_start=1,
                        line_end=1,
                        message=f"Maintainability index rank {rank}",
                        meta={"rank": rank, "mi": blocks.get("mi")},
                    )
                )
            continue

        # CC-style: list of function/class blocks.
        for block in blocks:
            rank = block.get("rank", "C")
            if rank in ("E", "F"):
                signals.append(
                    _emit(
                        tool="radon",
                        rule_id=f"ccn_{block.get('name', 'unknown')}",
                        raw_severity="high",
                        file_path=file_path,
                        line_start=block.get("line", 0),
                        line_end=block.get("endline", block.get("line", 0)),
                        message=(
                            f"Complexity rank {rank} in "
                            f"{block.get('type', 'block')} "
                            f"'{block.get('name', '')}'"
                        ),
                        meta={
                            "rank": rank,
                            "complexity": block.get("complexity"),
                            "block_type": block.get("type", ""),
                        },
                    )
                )
            elif rank == "D":
                signals.append(
                    _emit(
                        tool="radon",
                        rule_id=f"ccn_{block.get('name', 'unknown')}",
                        raw_severity="low",
                        file_path=file_path,
                        line_start=block.get("line", 0),
                        line_end=block.get("endline", block.get("line", 0)),
                        message=(
                            f"Complexity rank {rank} in "
                            f"{block.get('type', 'block')} "
                            f"'{block.get('name', '')}'"
                        ),
                        meta={
                            "rank": rank,
                            "complexity": block.get("complexity"),
                            "block_type": block.get("type", ""),
                        },
                    )
                )
    return signals


__all__ = [
    "normalize_semgrep",
    "normalize_bandit",
    "normalize_eslint",
    "normalize_gitleaks",
    "normalize_lizard",
    "normalize_radon",
]
