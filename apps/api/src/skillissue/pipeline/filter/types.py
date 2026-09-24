"""Data structures for the filter pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileInfo:
    """Metadata for a source file that passed all filters."""

    path: str       # relative path within the repo
    lang: str       # detected language (e.g. "python", "javascript")
    loc: int        # non-blank lines
    bytes: int      # file size in bytes
    sha1: str       # hex-encoded SHA-1 digest
