"""Hardened git clone fallback for tarball download failures."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class CloneError(Exception):
    """Raised when the git clone fallback fails."""


_GIT_TIMEOUT_SECONDS = 60


def git_clone(
    owner: str,
    repo: str,
    sha: str,
    dest_dir: Path,
    *,
    timeout: int = _GIT_TIMEOUT_SECONDS,
) -> Path:
    """Shallow clone a GitHub repo and checkout the given SHA.

    Uses hardened flags per ARCHITECTURE.md §7.2:
        --depth 1 --single-branch --no-tags --no-recurse-submodules
        core.symlinks=false, core.hooksPath=/dev/null,
        protocol.file.allow=never, transfer.fsckObjects=true

    Args:
        owner: Repository owner.
        repo: Repository name.
        sha: Commit SHA to checkout.
        dest_dir: Directory to clone into.
        timeout: Max seconds for the clone command.

    Returns:
        Path to the cloned repository.

    Raises:
        CloneError: If git is unavailable or the clone fails.
    """
    if shutil.which("git") is None:
        raise CloneError("git is not installed on this system")

    dest_dir.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://github.com/{owner}/{repo}.git"

    git_env = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": "/nonexistent",
    }

    git_cmd = [
        "git",
        "-c", "core.symlinks=false",
        "-c", "core.hooksPath=/dev/null",
        "-c", "protocol.file.allow=never",
        "-c", "transfer.fsckObjects=true",
        "clone",
        "--depth", "1",
        "--single-branch",
        "--no-tags",
        "--no-recurse-submodules",
        clone_url,
        str(dest_dir),
    ]

    try:
        result = subprocess.run(
            git_cmd,
            env={**git_env, **dict(__import__("os").environ)},
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise CloneError(
                f"git clone failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        raise CloneError(f"git clone timed out after {timeout} s")

    # Checkout the specific SHA
    checkout_result = subprocess.run(
        ["git", "-C", str(dest_dir), "checkout", "--force", sha],
        env=git_env,
        capture_output=True,
        text=True,
        timeout=timeout // 2,
    )
    if checkout_result.returncode != 0:
        raise CloneError(
            f"git checkout {sha} failed (exit {checkout_result.returncode}): "
            f"{checkout_result.stderr.strip()}"
        )

    # Remove .git directory (we have a clean working tree)
    git_dir = dest_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)

    return dest_dir
