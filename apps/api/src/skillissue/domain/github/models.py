"""Data models for GitHub API responses and repo metadata."""
from __future__ import annotations

from dataclasses import dataclass, field

from skillissue.domain.url.models import RepoRef


@dataclass(frozen=True)
class RepoMetadata:
    """Cached metadata for a GitHub repository."""

    full_name: str                  # canonical owner/repo (lowercased)
    default_branch: str             # e.g. "main"
    size_kb: int                    # repo size in KB from GitHub
    is_fork: bool
    is_archived: bool
    stargazers_count: int
    language: str | None
    commit_sha: str                 # HEAD SHA on the default branch
    etag: str                       # ETag header value for cache validation

    def exceeds_size_limit(self, max_mb: int) -> bool:
        """True if the repo exceeds max_mb megabytes."""
        return self.size_kb > max_mb * 1024
