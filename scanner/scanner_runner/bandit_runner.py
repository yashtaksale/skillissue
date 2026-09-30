"""Bandit runner: Python security linter."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_bandit(src_dir: Path, logs_dir: Path) -> dict:
    """Run Bandit on Python files and return normalized signals."""
    signals: list[dict] = []
    errors: list[str] = []

    if not src_dir.exists():
        return {"signals": signals, "errors": ["Source directory does not exist"]}

    try:
        result = subprocess.run(
            [
                "bandit",
                "-r", str(src_dir),
                "-f", "json",
                "--severity-level", "low",
                "--confidence-level", "low",
                "-x", ".venv,venv,node_modules,__pycache__,dist,build",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"signals": signals, "errors": ["bandit not installed"]}
    except subprocess.TimeoutExpired:
        return {"signals": signals, "errors": ["bandit timed out"]}

    # Bandit returns exit code 1 when findings exist, which is expected
    raw_output = result.stdout
    (logs_dir / "bandit_raw.json").write_text(raw_output or "{}", encoding="utf-8")

    if result.stderr:
        errors.append(f"bandit stderr: {result.stderr.strip()}")

    if not raw_output:
        return {"signals": signals, "errors": errors}

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return {"signals": signals, "errors": errors + [f"Failed to parse bandit JSON: {exc}"]}

    for finding in data.get("results", []):
        severity = finding.get("issue_severity", "MEDIUM").lower()
        confidence = finding.get("issue_confidence", "MEDIUM").lower()

        # Map Bandit confidence to 0-1 scale
        conf_map = {"high": 0.90, "medium": 0.70, "low": 0.50}
        conf_score = conf_map.get(confidence, 0.50)

        # Map Bandit severity
        sev_map = {"high": "high", "medium": "medium", "low": "low"}
        norm_severity = sev_map.get(severity, "medium")

        # Determine category from test ID
        test_id = finding.get("test_id", "")
        category = _categorize_bandit(test_id, finding.get("test_name", ""))

        # Make path relative to src_dir
        file_path = finding.get("filename", "")
        try:
            file_path = str(Path(file_path).relative_to(src_dir))
        except ValueError:
            pass

        signals.append({
            "tool": "bandit",
            "rule_id": test_id,
            "category": category,
            "severity": norm_severity,
            "confidence": conf_score,
            "file_path": file_path,
            "line_start": finding.get("line_number", 1),
            "line_end": finding.get("end_col_offset", finding.get("line_number", 1)),
            "message": finding.get("issue_text", ""),
            "snippet": finding.get("code", "")[:500],
        })

    return {"signals": signals, "errors": errors}


def _categorize_bandit(test_id: str, test_name: str) -> str:
    """Map Bandit test IDs to SkillIssue categories."""
    # B1xx: general security issues
    # B2xx: injection issues
    # B3xx: cryptographic issues
    # B4xx: network/web issues
    # B5xx: crypto issues
    # B6xx: import issues
    security_tests = {
        "B101", "B102", "B103", "B104", "B105", "B106", "B107", "B108",
        "B110",
        "B201", "B202",
        "B301", "B302", "B303", "B304", "B305", "B306", "B307", "B308",
        "B310", "B311", "B312", "B313", "B314", "B315", "B316", "B317",
        "B318", "B319", "B320", "B321", "B322", "B323", "B324",
        "B401", "B402", "B403", "B404", "B405", "B406", "B407", "B408",
        "B409", "B410", "B411", "B412", "B413",
        "B501", "B502", "B503", "B504", "B505", "B506", "B507",
        "B601", "B602", "B603", "B604", "B605", "B606", "B607", "B608",
        "B609", "B610", "B611", "B612",
        "B701", "B702", "B703",
    }
    if test_id in security_tests:
        return "security"

    name_lower = test_name.lower()
    if any(kw in name_lower for kw in ("inject", "xss", "exec", "shell", "crypto", "ssl", "tls", "secret")):
        return "security"

    return "bugs"
