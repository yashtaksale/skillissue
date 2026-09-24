"""Additional exceptions for GitHub API interactions."""
from __future__ import annotations

from skillissue.domain.url.exceptions import URLError


class GitHubAPIError(URLError):
    """Raised when the GitHub API returns an unexpected error."""


class RepoNotFoundError(GitHubAPIError):
    """Raised when the repository does not exist or is not public."""


class RateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is hit."""

    def __init__(self, message: str, *, reset_at: str = "") -> None:
        super().__init__(message)
        self.reset_at = reset_at


class EmptyRepoError(GitHubAPIError):
    """Raised when the repository exists but has no commits."""


class AuthenticationError(GitHubAPIError):
    """Raised when GitHub authentication fails (401)."""
