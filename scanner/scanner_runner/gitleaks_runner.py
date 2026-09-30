"""gitleaks runner: secret detection."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_gitleaks(src_dir: Path, logs_dir: Path) -> dict:
    """Run gitleaks to detect hardcoded secrets."""
    signals: list[dict] = []
    secret_spans: list[dict] = []
    errors: list[str] = []

    if not src_dir.exists():
        return {"signals": signals, "secret_spans": secret_spans, "errors": ["Source directory does not exist"]}

    report_path = logs_dir / "gitleaks_report.json"

    try:
        result = subprocess.run(
            [
                "gitleaks",
                "detect",
                "--source", str(src_dir),
                "--report-path", str(report_path),
                "--report-format", "json",
                "--no-git",
                "--exit-code", "0",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"signals": signals, "secret_spans": secret_spans, "errors": ["gitleaks not installed"]}
    except subprocess.TimeoutExpired:
        return {"signals": signals, "secret_spans": secret_spans, "errors": ["gitleaks timed out"]}

    (logs_dir / "gitleaks_stderr.txt").write_text(result.stderr or "", encoding="utf-8")

    if result.stderr:
        errors.append(f"gitleaks stderr: {result.stderr.strip()}")

    if not report_path.exists():
        return {"signals": signals, "secret_spans": secret_spans, "errors": errors}

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"signals": signals, "secret_spans": secret_spans, "errors": errors + [f"Failed to parse gitleaks JSON: {exc}"]}

    # Handle both old (list) and new (dict with "findings" key) gitleaks JSON schemas
    findings = []
    if isinstance(data, list):
        findings = data
    elif isinstance(data, dict) and "findings" in data:
        findings = data["findings"]
    elif isinstance(data, dict):
        # Single finding object
        findings = [data]

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        file_path = finding.get("File", "") or finding.get("file", "")
        try:
            file_path = str(Path(file_path).relative_to(src_dir))
        except ValueError:
            pass

        line = finding.get("StartLine", finding.get("line", 1))
        rule_id = finding.get("RuleID", finding.get("rule_id", "gitleaks/unknown"))

        # Mask the secret — RULES.md: full secrets never leave the scanner
        secret_value = finding.get("Secret", finding.get("secret", ""))
        masked = _mask_secret(secret_value)

        signals.append({
            "tool": "gitleaks",
            "rule_id": f"gitleaks/{rule_id}",
            "category": "security",
            "severity": "critical",
            "confidence": 0.92,
            "file_path": file_path,
            "line_start": line,
            "line_end": finding.get("EndLine", finding.get("end_line", line)),
            "message": f"Hardcoded secret detected: {finding.get('Description', finding.get('description', rule_id))}",
            "snippet": masked,
        })

        # Record the secret span for masking (without the actual value)
        secret_spans.append({
            "file_path": file_path,
            "line_start": line,
            "line_end": finding.get("EndLine", finding.get("end_line", line)),
            "col_start": finding.get("StartColumn", finding.get("start_column", 0)),
            "col_end": finding.get("EndColumn", finding.get("end_column", 0)),
            "rule_id": rule_id,
            "entropy": finding.get("Entropy", finding.get("entropy", 0)),
        })

    return {"signals": signals, "secret_spans": secret_spans, "errors": errors}


def _mask_secret(secret: str) -> str:
    """Mask a secret value per RULES.md: full secrets never leave the scanner."""
    if not secret:
        return "[REDACTED]"
    if len(secret) <= 8:
        return f"{secret[:2]}{'*' * (len(secret) - 2)}"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"
