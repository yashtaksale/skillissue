"""Scanner runner entrypoint.

Reads source from /work/src, runs all tools, writes:
  /out/signals.json      — normalized signals
  /out/secret_spans.json — masked secret locations
  /out/tool_logs/        — raw tool output
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from scanner_runner.bandit_runner import run_bandit
from scanner_runner.eslint_runner import run_eslint
from scanner_runner.gitleaks_runner import run_gitleaks
from scanner_runner.lizard_runner import run_lizard
from scanner_runner.radon_runner import run_radon
from scanner_runner.normalizer import normalize_signals


def main() -> None:
    src_dir = Path(os.environ.get("SCANNER_SRC_DIR", "/work/src"))
    out_dir = Path(os.environ.get("SCANNER_OUT_DIR", "/out"))
    logs_dir = out_dir / "tool_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        print(f"ERROR: Source directory {src_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    all_signals: list[dict] = []
    secret_spans: list[dict] = []

    # Run each tool and collect results
    tools = [
        ("bandit", run_bandit),
        ("eslint", run_eslint),
        ("gitleaks", run_gitleaks),
        ("lizard", run_lizard),
        ("radon", run_radon),
    ]

    for tool_name, runner in tools:
        try:
            print(f"Running {tool_name}...")
            result = runner(src_dir, logs_dir)
            if result.get("signals"):
                all_signals.extend(result["signals"])
            if result.get("secret_spans"):
                secret_spans.extend(result["secret_spans"])
            if result.get("errors"):
                for err in result["errors"]:
                    print(f"  {tool_name} error: {err}", file=sys.stderr)
            print(f"  {tool_name}: {len(result.get('signals', []))} signals")
        except Exception as exc:
            print(f"  {tool_name} failed: {exc}", file=sys.stderr)
            (logs_dir / f"{tool_name}_error.txt").write_text(str(exc))

    # Normalize all signals to common format
    normalized = normalize_signals(all_signals)

    # Write outputs
    (out_dir / "signals.json").write_text(
        json.dumps(normalized, indent=2), encoding="utf-8"
    )
    (out_dir / "secret_spans.json").write_text(
        json.dumps(secret_spans, indent=2), encoding="utf-8"
    )

    print(f"Scanner complete: {len(normalized)} signals, {len(secret_spans)} secret spans")


if __name__ == "__main__":
    main()
