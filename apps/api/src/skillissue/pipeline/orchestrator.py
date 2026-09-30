"""Phase-1 acquisition orchestration (Task T-1.5)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from skillissue.domain.url.models import RepoRef
from skillissue.pipeline.acquire.downloader import DownloadError, download_tarball
from skillissue.pipeline.acquire.extractor import ExtractError, safe_extract
from skillissue.pipeline.acquire.git_clone import CloneError, git_clone
from skillissue.pipeline.denylist import RepoOptedOutError, check_denylist


AcquisitionMethod = Literal["tarball", "git"]


class AcquisitionError(Exception):
    """Raised when both tarball and git clone fail."""


async def acquire_source(
    repo_ref: RepoRef,
    *,
    github_token: str | None = None,
    work_dir: Path | str | None = None,
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

    Returns:
        Tuple of (extracted source path, acquisition method).

    Raises:
        RepoOptedOutError: If repo is on the denylist.
        AcquisitionError: If both tarball and git clone fail.
    """
    # Check denylist first
    check_denylist(repo_ref)

    # Determine working directory
    base = (
        Path(work_dir)
        if work_dir
        else Path(tempfile.mkdtemp(prefix="skillissue_acquire_"))
    )

    # Try tarball first
    try:
        tarball_path = await download_tarball(
            repo_ref.owner,
            repo_ref.repo,
            repo_ref.ref,
            base,
            github_token=github_token or "",
        )
        try:
            safe_extract(tarball_path, base, strip_components=1)
            source_path = base / f"{repo_ref.repo}-{repo_ref.ref[:7]}"
            return source_path, "tarball"
        except ExtractError:
            # Extraction failed; fall through to git
            pass
    except DownloadError:
        # Download failed; fall through to git
        pass

    # Fall back to git clone
    try:
        source_path = _acquire_via_git(repo_ref, base)
        return source_path, "git"
    except CloneError as exc:
        raise AcquisitionError(
            f"Both tarball and git clone failed for {repo_ref.owner}/{repo_ref.repo}: {exc}"
        ) from exc


def _acquire_via_git(repo_ref: RepoRef, base: Path) -> Path:
    """Acquire source via git clone."""
    dest = base / f"{repo_ref.owner}_{repo_ref.repo}"
    dest.mkdir(parents=True, exist_ok=True)
    return git_clone(repo_ref.owner, repo_ref.repo, repo_ref.ref, dest)
