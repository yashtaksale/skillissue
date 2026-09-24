"""Tests for the hardened git clone fallback."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skillissue.pipeline.acquire.git_clone import CloneError, git_clone


def test_git_clone_raises_when_git_not_installed(tmp_path: Path) -> None:
    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value=None):
        with pytest.raises(CloneError, match="git is not installed"):
            git_clone("o", "r", "abc", tmp_path / "dest")


def test_git_clone_uses_hardened_flags(tmp_path: Path) -> None:
    captured_args: list[list[str]] = []

    def mock_run(args, **kwargs):
        captured_args.append(args)
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=mock_run):
            git_clone("octocat", "Hello-World", "abc1234def", tmp_path / "dest")

    clone_args = captured_args[0]
    assert clone_args[0] == "git"
    assert "core.symlinks=false" in clone_args
    assert "core.hooksPath=/dev/null" in clone_args
    assert "protocol.file.allow=never" in clone_args
    assert "transfer.fsckObjects=true" in clone_args
    assert "--depth" in clone_args
    assert "--no-tags" in clone_args
    assert "--single-branch" in clone_args
    assert "--no-recurse-submodules" in clone_args


def test_git_clone_sets_hardened_env_vars(tmp_path: Path) -> None:
    captured_env: dict = {}

    def mock_run(args, env=None, **kwargs):
        captured_env.update(env or {})
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=mock_run):
            git_clone("o", "r", "abc", tmp_path / "dest")

    assert captured_env.get("GIT_TERMINAL_PROMPT") == "0"
    assert captured_env.get("GIT_CONFIG_NOSYSTEM") == "1"
    assert captured_env.get("HOME") == "/nonexistent"


def test_git_clone_calls_rmtree_on_git_dir(tmp_path: Path) -> None:
    """Verify shutil.rmtree is called to remove .git after clone."""
    rmtree_calls: list = []

    def mock_run(args, **kwargs):
        # Simulate clone + checkout by creating .git on disk
        dest = Path(args[-1])
        if args[0] == "git" and "clone" in args:
            (dest / ".git").mkdir(parents=True, exist_ok=True)
        result = MagicMock()
        result.returncode = 0
        return result

    def mock_rmtree(path, **kwargs):
        rmtree_calls.append(path)

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=mock_run):
            with patch("shutil.rmtree", side_effect=mock_rmtree):
                git_clone("o", "r", "abc", tmp_path / "dest")

    # rmtree should have been called on the .git directory
    assert len(rmtree_calls) == 1
    assert ".git" in str(rmtree_calls[0])


def test_git_clone_raises_on_failure(tmp_path: Path) -> None:
    result = MagicMock()
    result.returncode = 1
    result.stderr = "fatal: repository not found"

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", return_value=result):
            with pytest.raises(CloneError, match="git clone failed"):
                git_clone("o", "r", "abc", tmp_path / "dest")


def test_git_clone_raises_on_timeout(tmp_path: Path) -> None:
    from subprocess import TimeoutExpired

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=TimeoutExpired("git", 60)):
            with pytest.raises(CloneError, match="timed out"):
                git_clone("o", "r", "abc", tmp_path / "dest")


def test_git_clone_checkout_specific_sha(tmp_path: Path) -> None:
    captured_args: list[str] = []

    def mock_run(args, **kwargs):
        captured_args.extend(args)
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=mock_run):
            git_clone("o", "r", "deadbeef" * 5, tmp_path / "dest")

    assert "checkout" in captured_args
    assert "deadbeef" * 5 in captured_args


def test_git_clone_uses_correct_clone_url(tmp_path: Path) -> None:
    captured_args: list[str] = []

    def mock_run(args, **kwargs):
        captured_args.extend(args)
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("skillissue.pipeline.acquire.git_clone.shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run", side_effect=mock_run):
            git_clone("torvalds", "linux", "abc123", tmp_path / "dest")

    # The clone URL should be in the args
    assert "https://github.com/torvalds/linux.git" in captured_args
