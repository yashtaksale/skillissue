"""Radon runner: Python maintainability index and complexity."""
from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path


def run_radon(src_dir: Path, logs_dir: Path) -> dict:
    """Run Radon for maintainability index on Python files."""
    signals: list[dict] = []
    errors: list[str] = []

    if not src_dir.exists():
        return {"signals": signals, "errors": ["Source directory does not exist"]}

    # Check for Python files first
    py_files = list(src_dir.rglob("*.py"))
    excluded = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    py_files = [f for f in py_files if not any(ex in f.parts for ex in excluded)]

    if not py_files:
        return {"signals": signals}

    # Run radon mi (maintainability index) with JSON output
    result = subprocess.run(
        [
            "radon", "mi",
            str(src_dir),
            "-j",
            "-e", "node_modules,*.venv,venv,__pycache__,dist,build",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    raw_output = result.stdout
    (logs_dir / "radon_mi_raw.json").write_text(raw_output or "{}", encoding="utf-8")

    if raw_output:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            data = {}
            errors.append(f"Failed to parse radon MI JSON: {exc}")

        for file_path_str, mi_info in data.items():
            if not isinstance(mi_info, dict):
                continue

            mi_value = mi_info.get("mi", 100.0)
            rank = mi_info.get("rank", "A")

            # Only flag C and below (poor maintainability)
            if rank in ("A", "B"):
                continue

            try:
                rel_path = str(Path(file_path_str).relative_to(src_dir))
            except ValueError:
                rel_path = file_path_str

            severity = "low"
            if rank in ("D", "F"):
                severity = "medium"
            elif rank == "C":
                severity = "low"

            signals.append({
                "tool": "radon",
                "rule_id": f"radon/maintainability-{rank.lower()}",
                "category": "maintainability",
                "severity": severity,
                "confidence": 0.90,
                "file_path": rel_path,
                "line_start": 1,
                "line_end": 1,
                "message": f"Low maintainability index: {mi_value:.1f} (rank {rank})",
                "snippet": f"MI: {mi_value:.1f}, Rank: {rank}",
            })

    # Also run radon cc (cyclomatic complexity) for detailed function-level data
    cc_result = subprocess.run(
        [
            "radon", "cc",
            str(src_dir),
            "--csv",
            "-n", "C",  # Only report C and worse
            "-e", "node_modules,*.venv,venv,__pycache__,dist,build",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    cc_output = cc_result.stdout
    (logs_dir / "radon_cc_raw.csv").write_text(cc_output or "", encoding="utf-8")

    if cc_output:
        try:
            # Parse CSV properly using csv module
            reader = csv.DictReader(io.StringIO(cc_output))
            for row in reader:
                try:
                    file_path_str = row.get("File", "").strip()
                    name = row.get("Function", row.get("Method", "unknown")).strip()
                    complexity = int(row.get("CCN", row.get("Complexity", "0")))
                    rank = row.get("Rank", "A")
                    line_start = int(row.get("Line", row.get("Lineno", "1")))
                    end_line = int(row.get("End Line", row.get("Endline", str(line_start))))
                except (ValueError, KeyError) as exc:
                    errors.append(f"Failed to parse radon CC row: {exc}, row={row}")
                    continue

                try:
                    rel_path = str(Path(file_path_str).relative_to(src_dir))
                except ValueError:
                    rel_path = file_path_str

                if rank in ("A", "B"):
                    continue

                severity = "low"
                if rank in ("E", "F"):
                    severity = "high"
                elif rank in ("C", "D"):
                    severity = "medium"

                signals.append({
                    "tool": "radon",
                    "rule_id": f"radon/complexity-{rank.lower()}",
                    "category": "maintainability",
                    "severity": severity,
                    "confidence": 0.95,
                    "file_path": rel_path,
                    "line_start": line_start,
                    "line_end": end_line,
                    "message": f"Function '{name}' has complexity rank {rank} (CC={complexity})",
                    "snippet": f"Cyclomatic Complexity: {complexity}, Rank: {rank}",
                })
        except Exception as exc:
            errors.append(f"Failed to parse radon CC CSV: {exc}")

    return {"signals": signals, "errors": errors}
