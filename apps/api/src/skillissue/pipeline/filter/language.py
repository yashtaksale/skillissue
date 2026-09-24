"""Language detection by file extension, basename, and shebang fallback."""
from __future__ import annotations

import os

_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "javascript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
}

# Basename checks (no extension, exact match).
_BASENAME_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "vagrantfile": "ruby",
}

_SHEBANG_MAP: dict[str, str] = {
    "python": "python",
    "python3": "python",
    "node": "javascript",
    "nodejs": "javascript",
    "bash": "shell",
    "sh": "shell",
    "ruby": "ruby",
    "perl": "perl",
    "php": "php",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "zsh": "shell",
    "fish": "shell",
    "kotlin": "kotlin",
    "scala": "scala",
    "swift": "swift",
    "lua": "lua",
    "r": "r",
    "groovy": "groovy",
    "groovysh": "groovy",
}


def detect(path: str, content_head: bytes = b"") -> str:
    """Detect the programming language of a source file.

    Detection order:
    1. File extension (case-insensitive).
    2. Basename match for extensionless files (Dockerfile, Makefile, etc.).
    3. Shebang fallback for extensionless files.

    Args:
        path: The file path (used for extension and basename lookup).
        content_head: First few bytes of the file for shebang detection
            (only used when the file has no recognized extension).

    Returns:
        Language name (e.g. "python", "javascript") or "unknown".
    """
    ext_start = path.rfind(".")
    if ext_start != -1:
        ext = path[ext_start:]
        lang = _EXT_MAP.get(ext.lower())
        if lang is not None:
            return lang

    # Basename fallback for extensionless files (Dockerfile, Makefile, etc.).
    basename = os.path.basename(path).lower()
    lang = _BASENAME_MAP.get(basename)
    if lang is not None:
        return lang

    # Shebang fallback for extensionless files
    head = content_head.lstrip()
    if head.startswith(b"#!"):
        shebang_line = head[:256].decode("utf-8", errors="replace").splitlines()[0]
        interpreter = _parse_shebang_interpreter(shebang_line)
        return _SHEBANG_MAP.get(interpreter, "unknown")

    return "unknown"


def _parse_shebang_interpreter(shebang_line: str) -> str:
    """Extract the interpreter name from a shebang line.

    Handles ``#!/usr/bin/env python3`` by returning ``"python3"``
    (skipping the ``env`` wrapper), and direct paths like
    ``#!/bin/bash`` by returning ``"bash"``.

    Args:
        shebang_line: The full shebang line (e.g. ``"#!/usr/bin/env python3"``).

    Returns:
        Lowercase interpreter name.
    """
    parts = shebang_line[2:].strip().split()
    # Handle "#!/usr/bin/env <interpreter>" → parts = ["/usr/bin/env", "python3"]
    if len(parts) >= 2 and parts[0].endswith("env"):
        return parts[1].lower()
    # Handle "#!/bin/bash" → parts = ["/bin/bash"]
    if parts:
        return parts[0].split("/")[-1].lower()
    return ""


