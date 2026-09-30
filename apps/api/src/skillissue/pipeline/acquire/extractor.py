"""Safe tar extractor with security checks."""
from __future__ import annotations

import os
import tarfile
from pathlib import Path


class ExtractError(Exception):
    """Raised when tar extraction fails due to a security violation."""


# Extraction limits from ARCHITECTURE.md §7.2
_MAX_ENTRIES = 50_000
_MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MB
_MAX_DEPTH = 40
_MAX_SINGLE_FILE = 50 * 1024 * 1024  # 50 MB
_MAX_NAME_LENGTH = 255
_FORBIDDEN_CHARS = frozenset(
    '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n'
    '\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14'
    '\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
)


def _check_member_name(name: str) -> None:
    """Validate a tar member name for path traversal and control chars."""
    if not name:
        raise ExtractError("Empty member name in tarball")

    if os.path.isabs(name):
        raise ExtractError(f"Absolute path in tarball member: {name!r}")

    parts = name.split("/")
    if ".." in parts:
        raise ExtractError(f"Path traversal (..) in tarball member: {name!r}")

    bad = [c for c in name if c in _FORBIDDEN_CHARS]
    if bad:
        raise ExtractError(
            f"Control characters in tarball member {name!r}: {bad!r}"
        )

    if len(name.encode("utf-8")) > _MAX_NAME_LENGTH:
        raise ExtractError(
            f"Tarball member name too long ({len(name.encode('utf-8'))} bytes): {name!r}"
        )

    depth = len(parts) if parts != [""] else 0
    if depth > _MAX_DEPTH:
        raise ExtractError(
            f"Tarball member exceeds max depth ({depth} > {_MAX_DEPTH}): {name!r}"
        )


_SKIP_TYPES = {
    tarfile.SYMTYPE,
    tarfile.LNKTYPE,
    tarfile.CHRTYPE,
    tarfile.BLKTYPE,
    tarfile.FIFOTYPE,
}


def safe_extract(
    tarball_path: str | Path,
    dest_dir: str | Path,
    *,
    strip_components: int = 0,
    max_entries: int = _MAX_ENTRIES,
    max_total_bytes: int = _MAX_TOTAL_UNCOMPRESSED,
) -> list[str]:
    """Extract a tarball safely to *dest_dir*.

    Args:
        tarball_path: Path to the .tar.gz file.
        dest_dir: Directory to extract into.
        strip_components: Number of leading path components to strip.
        max_entries: Maximum number of members to extract.
        max_total_bytes: Maximum total uncompressed bytes.

    Returns:
        List of relative paths that were extracted.

    Raises:
        ExtractError: If any security check fails.
    """
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Use a temp dir for extraction to prevent TOCTOU / symlink races
    import tempfile
    with tempfile.TemporaryDirectory(prefix="skillissue_extract_", dir=dest_dir.parent) as tmp_extract:
        tmp_extract_path = Path(tmp_extract)

        extracted: list[str] = []
        total_bytes = 0

        with tarfile.open(tarball_path, mode="r:gz") as tf:
            members = tf.getmembers()

            if len(members) > max_entries:
                raise ExtractError(
                    f"Tarball has {len(members)} entries, exceeding limit of {max_entries}"
                )

            for member in members:
                parts = member.name.split("/")
                if len(parts) <= strip_components:
                    continue
                stripped_name = "/".join(parts[strip_components:])
                if not stripped_name:
                    continue

                _check_member_name(stripped_name)

                if member.type in _SKIP_TYPES:
                    # Explicitly skip symlinks, hardlinks, device files, etc.
                    continue

                if member.size > _MAX_SINGLE_FILE:
                    continue

                total_bytes += member.size
                if total_bytes > max_total_bytes:
                    raise ExtractError(
                        f"Uncompressed total ({total_bytes // (1024 * 1024)} MB) "
                        f"exceeds limit ({max_total_bytes // (1024 * 1024)} MB)"
                    )

                dest_path = tmp_extract_path / stripped_name

                # Security: ensure dest_path stays within tmp_extract_path
                try:
                    dest_path.relative_to(tmp_extract_path)
                except ValueError:
                    raise ExtractError(f"Path traversal attempt detected: {stripped_name}")

                if member.isdir():
                    dest_path.mkdir(parents=True, exist_ok=True)
                    dest_path.chmod(0o755)
                elif member.isfile():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    source = tf.extractfile(member)
                    if source is None:
                        continue
                    data = source.read()
                    dest_path.write_bytes(data)
                    dest_path.chmod(0o644)
                    extracted.append(stripped_name)

        # Atomically move extracted files to final destination
        for rel_path in extracted:
            src = tmp_extract_path / rel_path
            dst = dest_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                if dst.exists():
                    import shutil
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                import shutil
                shutil.move(str(src), str(dst))

    return extracted
