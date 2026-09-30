"""Lizard runner: cyclomatic complexity analysis."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_lizard(src_dir: Path, logs_dir: Path) -> dict:
    """Run Lizard for cyclomatic complexity metrics."""
    signals: list[dict] = []
    errors: list[str] = []

    if not src_dir.exists():
        return {"signals": signals, "errors": ["Source directory does not exist"]}

    try:
        result = subprocess.run(
            [
                "lizard",
                str(src_dir),
                "--csv",
                "-T", "cyclomatic_complexity=15",
                "-l", "python",
                "-l", "javascript",
                "-l", "typescript",
                "--exclude", "*/node_modules/*",
                "--exclude", "*/.venv/*",
                "--exclude", "*/dist/*",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"signals": signals, "errors": ["lizard not installed"]}
    except subprocess.TimeoutExpired:
        return {"signals": signals, "errors": ["lizard timed out"]}

    raw_output = result.stdout
    (logs_dir / "lizard_raw.csv").write_text(raw_output or "", encoding="utf-8")

    if result.stderr:
        errors.append(f"lizard stderr: {result.stderr.strip()}")

    if not raw_output:
        return {"signals": signals, "errors": errors}

    # Parse CSV output: NLOC, CCN, Token, PARAM, Length, Location, File, Args, ...
    for line in raw_output.strip().split("\n"):
        if not line or line.startswith("NLOC"):
            continue

        parts = line.split(",")
        if len(parts) < 7:
            continue

        try:
            nloc = int(parts[0].strip())
            ccn = int(parts[1].strip())
            token_count = int(parts[2].strip())
            param_count = int(parts[3].strip())
            length = int(parts[4].strip())
            location = parts[5].strip().strip('"')
            file_path = parts[6].strip().strip('"')
        except (ValueError, IndexError):
            continue

        # Only flag high complexity
        if ccn < 10:
            continue

        # Make path relative
        try:
            file_path = str(Path(file_path).relative_to(src_dir))
        except ValueError:
            pass

        # Parse location for line number
        line_num = 1
        func_name = location
        if "@" in location:
            func_name, loc_part = location.rsplit("@", 1)
            try:
                line_num = int(loc_part)
            except ValueError:
                pass

        severity = "low"
        if ccn >= 25:
            severity = "high"
        elif ccn >= 15:
            severity = "medium"

        signals.append({
            "tool": "lizard",
            "rule_id": "lizard/cyclomatic-complexity",
            "category": "maintainability",
            "severity": severity,
            "confidence": 0.95,  # Deterministic tool
            "file_path": file_path,
            "line_start": line_num,
            "line_end": line_num + length,
            "message": f"Function '{func_name}' has cyclomatic complexity {ccn} (threshold: 15)",
            "snippet": f"CCN: {ccn}, NLOC: {nloc}, Parameters: {param_count}",
        })

    return {"signals": signals, "errors": errors}
