"""Denylist and opt-out checks for repo acquisition."""
from __future__ import annotations

from pathlib import Path

from skillissue.domain.url.models import RepoRef

# Default denylist (placeholder; real implementation loads from DB/config)
_DEFAULT_DENYLIST: set[str] = set()

OPTOUT_FILE_NAME = "skillissue-optout"


class RepoOptedOutError(Exception):
    """Raised when a repo is in the denylist or contains optout file."""


def _normalize_owner(owner: str) -> str:
    return owner.casefold()


def _normalize_repo(repo: str) -> str:
    return repo.casefold()


def is_denylisted(
    repo_ref: RepoRef,
    denylist: set[str] | None = None,
) -> bool:
    """Check if a repo (owner or owner/repo) is in the denylist.

    Args:
        repo_ref: The repo reference to check.
        denylist: Optional denylist set (case-folded entries).
            Defaults to empty.

    Returns:
        True if either the owner or owner/repo is denylisted.
    """
    denylist = denylist if denylist is not None else _DEFAULT_DENYLIST
    owner_lc = _normalize_owner(repo_ref.owner)
    repo_lc = _normalize_repo(repo_ref.repo)
    full = f"{owner_lc}/{repo_lc}"
    return owner_lc in denylist or full in denylist


def check_denylist(
    repo_ref: RepoRef,
    denylist: set[str] | None = None,
) -> None:
    """Raise RepoOptedOutError if the repo is denylisted.

    Args:
        repo_ref: The repo reference to check.
        denylist: Optional denylist set.

    Raises:
        RepoOptedOutError: If owner or owner/repo is denylisted.
    """
    if is_denylisted(repo_ref, denylist):
        owner_lc = _normalize_owner(repo_ref.owner)
        repo_lc = _normalize_repo(repo_ref.repo)
        full = f"{owner_lc}/{repo_lc}"
        raise RepoOptedOutError(
            f"Repository {repo_ref.full_name} has opted out (matched {full!r} or owner)"
        )


def check_optout_file(repo_root: Path | str) -> bool:
    """Return True if the repo has a skillissue-optout file at the root.

    Args:
        repo_root: Path to the extracted repo.

    Returns:
        True if opt-out file exists.
    """
    repo_root = Path(repo_root)
    return (repo_root / OPTOUT_FILE_NAME).is_file()


def check_optout(repo_ref: RepoRef, repo_root: Path | str) -> None:
    """Raise RepoOptedOutError if the repo contains an opt-out file.

    Args:
        repo_ref: The repo reference.
        repo_root: Path to the extracted repo.

    Raises:
        RepoOptedOutError: If skillissue-optout file is found.
    """
    if check_optout_file(repo_root):
        raise RepoOptedOutError(
            f"Repository {repo_ref.full_name} contains {OPTOUT_FILE_NAME}; "
            f"opt-out honored"
        )
