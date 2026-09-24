"""Snippet builder: reads source lines from a file on disk."""
from __future__ import annotations

import pathlib


def build_snippet(file_path: str, line_start: int, line_end: int, lines: list[str]) -> str:
    """Return the source text spanning *line_start* through *line_end* (1-based, inclusive).

    When *lines* is already provided the function simply slices and joins
    them.  When *lines* is empty the file is read from *file_path*.

    Args:
        file_path: Absolute or repo-relative path to the source file.
        line_start: First line number (1-based, inclusive).
        line_end:   Last line number (1-based, inclusive).
        lines:      Optional pre-read list of lines (may be empty).

    Returns:
        Source text with line numbers preserved as a prefix on each line.
    """
    if not lines:
        try:
            path = pathlib.Path(file_path)
            if path.exists():
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []

    # Guard against empty or out-of-range inputs.
    if not lines or line_start < 1 or line_end < line_start:
        return ""

    # Convert 1-based to 0-based indices and clamp.
    start_idx = max(0, line_start - 1)
    end_idx = min(len(lines), line_end)

    selected = lines[start_idx:end_idx]
    return "\n".join(
        f"{i + line_start}│{line}"
        for i, line in enumerate(selected)
    )


__all__ = ["build_snippet"]
