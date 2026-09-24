"""Data model for parsed repo references."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoRef:
    """Canonical representation of a GitHub repo reference."""

    owner: str
    repo: str
    ref: str | None = None  # branch/tag name, or None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def __str__(self) -> str:
        if self.ref:
            return f"{self.owner}/{self.repo} (ref={self.ref})"
        return self.full_name
