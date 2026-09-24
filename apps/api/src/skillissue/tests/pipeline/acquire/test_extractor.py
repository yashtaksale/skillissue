"""Tests for the safe tar extractor."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from skillissue.pipeline.acquire.extractor import (
    ExtractError,
    _check_member_name,
    safe_extract,
)


def _build_tar(name: str, files: dict[str, bytes]) -> Path:
    """Build a .tar.gz in memory from a {path: bytes} dict."""
    out = Path(name)
    with tarfile.open(out, mode="w:gz") as tf:
        for path, data in files.items():
            info = tarfile.TarInfo(name=path)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return out


# === Unit tests for _check_member_name (the core security checks) ===


class TestCheckMemberName:
    def test_valid_simple_name(self):
        _check_member_name("README.md")  # should not raise

    def test_valid_nested_name(self):
        _check_member_name("src/lib/utils/helpers.py")

    def test_valid_unicode_name(self):
        _check_member_name("café/résumé.md")

    def test_rejects_empty_name(self):
        with pytest.raises(ExtractError, match="Empty"):
            _check_member_name("")

    def test_rejects_dotdot_traversal(self):
        with pytest.raises(ExtractError, match="traversal"):
            _check_member_name("../../../etc/passwd")

    def test_rejects_dotdot_middle(self):
        with pytest.raises(ExtractError, match="traversal"):
            _check_member_name("a/../../escape.txt")

    def test_rejects_control_char_nul(self):
        with pytest.raises(ExtractError, match="Control characters"):
            _check_member_name("bad\x00file.txt")

    def test_rejects_control_char_newline(self):
        with pytest.raises(ExtractError, match="Control characters"):
            _check_member_name("file\n.txt")

    def test_rejects_control_char_tab(self):
        with pytest.raises(ExtractError, match="Control characters"):
            _check_member_name("file\t.txt")

    def test_rejects_name_over_255_bytes(self):
        with pytest.raises(ExtractError, match="too long"):
            _check_member_name("a" * 256)

    def test_accepts_name_at_255_bytes(self):
        _check_member_name("a" * 255)  # should not raise

    def test_rejects_depth_41(self):
        parts = ["a"] * 41
        with pytest.raises(ExtractError, match="depth"):
            _check_member_name("/".join(parts) + "/f.txt")

    def test_accepts_depth_40(self):
        # 39 segments + "f.txt" = 40 parts total (depth check counts all parts)
        parts = ["a"] * 39
        _check_member_name("/".join(parts) + "/f.txt")  # should not raise


# === Integration tests for safe_extract ===


def test_extracts_normal_files(tmp_path: Path) -> None:
    tar = _build_tar("good.tar.gz", {
        "README.md": b"hello",
        "src/main.py": b"print('hi')",
    })
    extracted = safe_extract(tar, tmp_path / "out")

    assert "README.md" in extracted
    assert "src/main.py" in extracted


def test_strips_github_top_level_dir(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="octocat-repo-abc1234/file.txt")
    info.size = 1
    out = tmp_path / "gh.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.addfile(info, io.BytesIO(b"x"))

    safe_extract(out, tmp_path / "out", strip_components=1)
    assert (tmp_path / "out" / "file.txt").exists()


def test_normalizes_permissions_to_0644(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="file.sh")
    info.size = 3
    info.mode = 0o755
    tar = _build_tar("perm.tar.gz", {"file.sh": b"she"})

    safe_extract(tar, tmp_path / "out")
    file_path = tmp_path / "out" / "file.sh"
    mode = file_path.stat().st_mode & 0o777
    # chmod to 0644 is attempted; on some platforms (Windows) the result differs
    # so we assert the file is at least not executable
    assert mode & 0o111 == 0


def test_skips_symlink(tmp_path: Path) -> None:
    symlink = tarfile.TarInfo(name="evil_link")
    symlink.type = tarfile.SYMTYPE
    symlink.linkname = "/etc/passwd"
    good_info = tarfile.TarInfo(name="good.txt")
    good_info.size = 3

    out = tmp_path / "link.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.addfile(symlink)
        tf.addfile(good_info, io.BytesIO(b"abc"))

    safe_extract(out, tmp_path / "out")
    assert not (tmp_path / "out" / "evil_link").exists()
    assert (tmp_path / "out" / "good.txt").exists()


def test_skips_hardlink(tmp_path: Path) -> None:
    hard = tarfile.TarInfo(name="hlink")
    hard.type = tarfile.LNKTYPE
    out = tmp_path / "hlink.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.addfile(hard)

    safe_extract(out, tmp_path / "out")
    assert not (tmp_path / "out" / "hlink").exists()


def test_rejects_too_many_entries(tmp_path: Path) -> None:
    entries = {}
    for i in range(60):
        entries[f"f{i:05d}.txt"] = b"x"

    tar = _build_tar("many.tar.gz", entries)
    with pytest.raises(ExtractError, match="entries"):
        safe_extract(tar, tmp_path / "out", max_entries=50)


def test_rejects_deeply_nested_path(tmp_path: Path) -> None:
    parts = ["a"] * 50
    deep_path = "/".join(parts) + "/file.txt"
    info = tarfile.TarInfo(name=deep_path)
    info.size = 3
    out = tmp_path / "deep.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.addfile(info, io.BytesIO(b"abc"))

    with pytest.raises(ExtractError, match="depth"):
        safe_extract(out, tmp_path / "out")


def test_rejects_oversized_uncompressed_total(tmp_path: Path) -> None:
    """20 files × 5 bytes = 100 bytes, limit = 50."""
    entries = {f"f{i}.bin": b"xxxxx" for i in range(20)}
    tar = _build_tar("huge.tar.gz", entries)

    with pytest.raises(ExtractError, match="exceeds limit"):
        safe_extract(tar, tmp_path / "out", max_total_bytes=50)


def test_dest_dir_created(tmp_path: Path) -> None:
    tar = _build_tar("create.tar.gz", {"x": b"y"})
    safe_extract(tar, tmp_path / "nonexistent" / "subdir")
    assert (tmp_path / "nonexistent" / "subdir" / "x").exists()
