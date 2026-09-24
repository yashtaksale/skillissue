"""Phase-1 acquisition orchestration (Task T-5)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from skillissue.domain.url.models import RepoRef
from skillissue.pipeline.acquire.downloader import AcquisitionResult, download_tarball
from skillissue.pipeline.acquire.extractor import ExtractionResult, safe_extract
from skillissue.pipeline.acquire.git_clone import git_clone
from skillissue.pipeline.denylist import RepoOptedOutError, check_denylist


AcquisitionMethod = Literal["tarball", "git"]


async def acquire_source(
    repo_ref: RepoRef,
    *,
    github_token: str | None = None,
    work_dir: Path | str | None = None,
    github_token_deprecated: str | None = None,
) -> tuple[Path, AcquisitionMethod]:
    """Acquire source code for a GitHub repo.

    Strategy (per ARCHITECTURE.md §7.2):
    1. Check denylist
    2. Try tarball download (preferred)
    3. Fall back to git clone if tarball fails

    Args:
        repo_ref: Parsed repository reference.
        github_token: GitHub API token (for tarball download).
        work_dir: Working directory for extraction (default: temp dir).
        github_token_deprecated: Deprecated alias for github_token.

    Returns:
        Tuple of (extracted source path, acquisition method).

    Raises:
        RepoOptedOutError: If repo is on the denylist.
        AcquisitionError: If both tarball and git clone fail.
    """
    # Backwards-compat: accept old kwarg name
    if github_token_deprecated and not github_token:
        github_token = github_token_deprecated

    # Check denylist first
    check_denylist(repo_ref)

    # Determine working directory
    base = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="skillissue_acquire_"))

    # Try tarball first
    result = await download_tarball(repo_ref, github_token=github_token)
    tarball_path = result.path

    try:
        extract_result = safe_extract(tarball_path, base)
        source_path = extract_result.path
        return source_path, "tarball"
    except Exception:
        # Fall back to git clone
        return _acquire_via_git(repo_ref, base), "git"


def _acquire_via_git(repo_ref: RepoRef, base: Path) -> Path:
    """Acquire source via git clone."""
    dest = base / f"{repo_ref.owner}_{repo_ref.repo}"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        git_clone(repo_ref.owner, repo_ref.repo, repo_ref.ref, dest)
    except CloneError as exc:
        raise RuntimeError(f"Both tarball and git clone failed: {exc}") from exc
    return dest
