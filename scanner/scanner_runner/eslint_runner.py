"""ESLint runner: JavaScript/TypeScript linter with security plugins."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def run_eslint(src_dir: Path, logs_dir: Path) -> dict:
    """Run ESLint on JS/TS files and return normalized signals."""
    signals: list[dict] = []
    errors: list[str] = []

    if not src_dir.exists():
        return {"signals": signals, "errors": ["Source directory does not exist"]}

    # Check if there are any JS/TS files
    js_files = list(src_dir.rglob("*.js")) + list(src_dir.rglob("*.ts"))
    js_files += list(src_dir.rglob("*.jsx")) + list(src_dir.rglob("*.tsx"))

    # Filter out node_modules and other excluded dirs
    excluded = {"node_modules", ".next", "dist", "build", "coverage", ".venv"}
    js_files = [
        f for f in js_files
        if not any(ex in f.parts for ex in excluded)
    ]

    if not js_files:
        return {"signals": signals, "errors": errors}

    # Create a flat config for ESLint 9
    config_content = """\
import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },
    rules: {
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-unused-vars": "warn",
      "no-undef": "warn",
      "no-empty-pattern": "warn",
      "no-fallthrough": "warn",
      "no-redeclare": "warn",
    },
  },
  {
    ignores: ["node_modules/**", "dist/**", "build/**", ".next/**", "coverage/**"],
  },
];
"""
    config_path = src_dir / "eslint.config.mjs"
    config_existed = config_path.exists()

    if not config_existed:
        config_path.write_text(config_content, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                "eslint",
                "--format", "json",
                "--no-error-on-unmatched-pattern",
                str(src_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(src_dir),
        )
    except FileNotFoundError:
        if not config_existed and config_path.exists():
            config_path.unlink()
        return {"signals": signals, "errors": ["eslint not installed"]}
    except subprocess.TimeoutExpired:
        if not config_existed and config_path.exists():
            config_path.unlink()
        return {"signals": signals, "errors": ["eslint timed out"]}

    raw_output = result.stdout
    (logs_dir / "eslint_raw.json").write_text(raw_output or "[]", encoding="utf-8")

    if result.stderr:
        errors.append(f"eslint stderr: {result.stderr.strip()}")

    if not raw_output:
        if not config_existed and config_path.exists():
            config_path.unlink()
        return {"signals": signals, "errors": errors}

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        if not config_existed and config_path.exists():
            config_path.unlink()
        return {"signals": signals, "errors": errors + [f"Failed to parse eslint JSON: {exc}"]}

    for file_result in data:
        file_path = file_result.get("filePath", "")
        try:
            file_path = str(Path(file_path).relative_to(src_dir))
        except ValueError:
            pass

        for msg in file_result.get("messages", []):
            severity = "medium" if msg.get("severity", 1) == 2 else "low"
            rule_id = msg.get("ruleId", "eslint/unknown")
            category = _categorize_eslint(rule_id)

            signals.append({
                "tool": "eslint",
                "rule_id": f"eslint/{rule_id}" if "/" not in (rule_id or "") else rule_id,
                "category": category,
                "severity": severity,
                "confidence": 0.85,
                "file_path": file_path,
                "line_start": msg.get("line", 1),
                "line_end": msg.get("endLine", msg.get("line", 1)),
                "message": msg.get("message", ""),
                "snippet": "",
            })

    if not config_existed and config_path.exists():
        config_path.unlink()

    return {"signals": signals, "errors": errors}


def _categorize_eslint(rule_id: str | None) -> str:
    """Map ESLint rule IDs to categories."""
    if not rule_id:
        return "maintainability"

    security_rules = {
        "no-eval", "no-implied-eval", "no-new-func",
        "security/detect-eval-with-expression",
        "security/detect-non-literal-fs-filename",
        "security/detect-non-literal-regexp",
        "security/detect-no-csrf-before-method-override",
        "security/detect-object-injection",
        "security/detect-possible-timing-attacks",
        "security/detect-unsafe-regex",
        "no-unsanitized/method",
        "no-unsanitized/property",
    }
    if rule_id in security_rules:
        return "security"

    bug_rules = {
        "no-undef", "no-unused-vars", "no-redeclare",
        "no-fallthrough", "no-empty-pattern", "no-dupe-keys",
        "no-duplicate-case", "no-unreachable", "no-constant-condition",
        "no-self-assign", "no-self-compare", "use-isnan",
        "valid-typeof", "no-sparse-arrays",
    }
    if rule_id in bug_rules:
        return "bugs"

    return "maintainability"
