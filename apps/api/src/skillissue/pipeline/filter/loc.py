"""Line-of-code (LOC) counter with comment stripping."""
from __future__ import annotations

# Per-language line comment markers (simple prefix match, no string-literal awareness)
_COMMENT_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("#",),
    "javascript": ("//",),
    "typescript": ("//",),
    "go": ("//",),
    "rust": ("//",),
    "java": ("//",),
    "ruby": ("#",),
    "php": ("//", "#"),
    "csharp": ("//",),
    "cpp": ("//",),
    "swift": ("//",),
    "kotlin": ("//",),
    "scala": ("//",),
    "html": ("<!--",),
    "css": ("//",),
    "shell": ("#",),
    "sql": ("--",),
}


def count_loc(content: str, lang: str) -> tuple[int, int]:
    """Count total and non-blank (non-comment) lines.

    Blank lines and lines that consist solely of a comment are excluded
    from the non-blank count.  No string-literal or block-comment parsing
    is performed (MVP scope).

    Args:
        content: Full file text.
        lang: Detected language key.

    Returns:
        (total_lines, non_blank_lines) tuple.
    """
    lines = content.splitlines()
    total = len(lines)

    markers = _COMMENT_MARKERS.get(lang, ())
    non_blank = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        is_comment = any(stripped.startswith(m) for m in markers)
        if not is_comment:
            non_blank += 1

    return total, non_blank
