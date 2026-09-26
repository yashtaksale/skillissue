"""CLI: `python -m skillissue.cli sample <source_dir>`.

Shows which chunks would go to the LLM and why — the sampling demo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Sample a source directory and print chunk info."""
    parser = argparse.ArgumentParser(
        prog="skillissue-cli sample",
        description="SkillIssue — show LLM sampling plan for a source directory.",
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Path to the extracted source directory.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=150_000,
        help="Maximum total tokens (default: 150000).",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=30,
        help="Maximum number of chunks (default: 30).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )

    args = parser.parse_args(argv)

    source_dir = args.source_dir
    if not source_dir.is_dir():
        print(f"error: {source_dir} is not a directory", file=sys.stderr)
        return 2

    # 1. Collect source files
    from skillissue.pipeline.filter.language import detect as detect_lang
    from skillissue.pipeline.filter.loc import count_loc
    from skillissue.pipeline.filter.walker import walk

    print(f"Walking {source_dir}...", file=sys.stderr)
    result = walk(source_dir)

    if not result.files:
        print("No source files found.", file=sys.stderr)
        return 0

    file_paths = [f.path for f in result.files]
    file_lines = {f.path: f.loc for f in result.files}

    # 2. Score files
    from skillissue.pipeline.sample.scorer import score_files
    scores = score_files(file_paths, file_lines, source_dir=source_dir)

    # 3. Build dummy signals for forced inclusion demo
    from skillissue.pipeline.sample.selector import SignalInfo, select_files, SelectorConfig

    # Create fake signals for high-scoring files to demo forced inclusion
    signals = [
        SignalInfo(
            signal_id=f"sig_{i}",
            file=scores[i].path,
            severity="high" if scores[i].risk_score >= 0.5 else "medium",
            category="security",
        )
        for i in range(min(5, len(scores)))
        if scores[i].risk_score >= 0.3
    ]

    config = SelectorConfig(
        max_chunks=args.max_chunks,
        max_tokens=args.max_tokens,
    )

    # 4. Select files and produce chunks
    chunks, unselected = select_files(scores, signals=signals, source_dir=source_dir, config=config)

    # 5. Render output
    total_tokens = sum(c.estimated_tokens for c in chunks)
    total_files = sum(len(c.files) for c in chunks)

    if args.format == "json":
        output = {
            "source_dir": str(source_dir),
            "total_files": total_files,
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "max_tokens": args.max_tokens,
            "chunks": [
                {
                    "id": c.chunk_id,
                    "files": c.files,
                    "estimated_tokens": c.estimated_tokens,
                    "lines": c.total_lines,
                    "reason": c.selection_reason,
                    "overlap_with": c.overlap_with,
                }
                for c in chunks
            ],
            "unselected_count": len(unselected),
            "unselected": unselected[:10],
            "signals_forced": len(signals),
        }
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  Sampling plan: {source_dir}", file=sys.stderr)
        print(f"  Files: {total_files}/{len(file_paths)} selected", file=sys.stderr)
        print(f"  Chunks: {len(chunks)} (budget: {args.max_chunks})", file=sys.stderr)
        print(f"  Tokens: ~{total_tokens:,} / {args.max_tokens:,}", file=sys.stderr)
        print(f"  Forced inclusions (signals): {len(signals)}", file=sys.stderr)
        print(f"  Unselected: {len(unselected)}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)

        for c in chunks:
            overlap_note = f" (overlaps chunk {c.overlap_with})" if c.overlap_with >= 0 else ""
            print(f"Chunk {c.chunk_id}: {len(c.files)} files, ~{c.estimated_tokens:,} tokens{overlap_note}")
            print(f"  Reason: {c.selection_reason}")
            for f in c.files[:8]:
                print(f"    {f}")
            if len(c.files) > 8:
                print(f"    ... and {len(c.files) - 8} more")
            print()

        if unselected:
            print(f"--- {len(unselected)} unselected files ---")
            for f in unselected[:10]:
                print(f"  {f}")
            if len(unselected) > 10:
                print(f"  ... and {len(unselected) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
