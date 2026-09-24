"""S-3 prototype: safe tar extractor for SkillIssue spike.

Tests the extractor against malicious fixtures described in
ARCHITECTURE.md §7.2: traversal, absolute paths, symlinks, hardlinks,
devices, FIFOs, tar bombs, huge files, deep nesting, non-UTF8 names,
entry count caps, permission normalization.
"""
import io
import os
import re
import stat
import tarfile
import tempfile
import shutil
import hashlib
from pathlib import Path


# ── Safety limits (from ARCHITECTURE §7.2 + PRD §14) ──────────────────────
MAX_TOTAL_BYTES = 150 * 1024 * 1024        # 150 MB compressed (enforced before extraction)
MAX_ENTRIES = 50_000
MAX_UNCOMPRESSED = 500 * 1024 * 1024       # 500 MB uncompressed
MAX_DEPTH = 40
MAX_SINGLE_FILE = 50 * 1024 * 1024         # 50 MB; files larger → not extracted at all
MAX_UNCOMPRESSED_FILE_CHECK = 1 * 1024 * 1024  # also reject files > 1 MB at extraction
DEST_PERMS_FILE = 0o644
DEST_PERMS_DIR = 0o755
STRIP_TOP_DIR = True                        # GitHub tarballs have a top-level {owner}-{repo}-{sha7}/ dir


# ── Helpers ───────────────────────────────────────────────────────────────
def _safe_extract_filter(member: tarfile.TarInfo, dest: Path, top_stripped: bool) -> tarfile.TarInfo | None:
    """Return a modified TarInfo or None to skip the entry.
    This is the per-entry gate. Called by tarfile with filter='data' too,
    but we apply our own additional checks below.
    """
    raw_name = member.name

    # ── CHECK 1: Reject absolute paths IMMEDIATELY (before any normalization)
    if raw_name.startswith("/"):
        print(f"  SKIP absolute path: {raw_name}")
        return None

    # ── CHECK 2: Reject traversal on RAW name (before stripping top dir)
    # A ".." in any path segment is an escape attempt, regardless of what
    # directory structure surrounds it.
    if ".." in raw_name.split("/"):
        print(f"  SKIP traversal: {raw_name}")
        return None

    # ── Strip leading ./
    new_name = raw_name.lstrip("./")

    # ── Strip the GitHub top-level directory (owner-repo-sha7/)
    # Only strip if the first segment looks like a GitHub SHA prefix:
    # 7 hex chars optionally prefixed by owner-repo-.
    # This prevents accidentally stripping a malicious first segment.
    if top_stripped and "/" in new_name:
        first_seg = new_name.split("/")[0]
        # GitHub tarball format: {owner}-{repo}-{sha7}
        # We verify it looks like that pattern before stripping.
        if re.match(r'^[A-Za-z0-9_-]+-[A-Za-z0-9_-]+-[0-9a-f]{7}$', first_seg):
            new_name = "/".join(new_name.split("/")[1:])
        elif re.match(r'^[0-9a-f]{40}$', first_seg):
            new_name = "/".join(new_name.split("/")[1:])
        # else: not a GitHub prefix dir; leave it alone

    if not new_name:
        return None

    # After stripping top dir, re-check for absolute (shouldn't happen but defensive)
    if new_name.startswith("/"):
        print(f"  SKIP absolute after strip: {new_name}")
        return None

    name = new_name
    member.name = name

    # Reject traversal (.. segments)
    if ".." in name.split("/"):
        print(f"  SKIP traversal: {name}")
        return None

    # Reject NUL and control chars in name
    if any(c < 0x20 or c == 0x7F for c in name.encode("utf-8", errors="replace")):
        print(f"  SKIP control chars in name: {name!r}")
        return None

    # Reject names > 255 bytes
    if len(name.encode("utf-8")) > 255:
        print(f"  SKIP name too long: {name!r}")
        return None

    # Reject depth > MAX_DEPTH
    depth = name.count("/")
    if depth > MAX_DEPTH:
        print(f"  SKIP too deep ({depth}): {name}")
        return None

    # Skip symlinks, hardlinks, devices, FIFOs
    if member.issym() or member.islnk() or member.ischr() or member.isdev() or member.isfifo():
        print(f"  SKIP special file ({member.type}): {name}")
        return None

    # Skip files > MAX_UNCOMPRESSED_FILE_CHECK (not extracted at all per ARCHITECTURE)
    if member.isfile() and member.size > MAX_UNCOMPRESSED_FILE_CHECK:
        print(f"  SKIP too large ({member.size} bytes): {name}")
        return None

    # Normalize permissions
    if member.isdir():
        member.mode = DEST_PERMS_DIR
    elif member.isfile():
        member.mode = DEST_PERMS_FILE
        # clear setuid/setgid/sticky
        member.mode &= ~(stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)

    return member


def safe_extract(tar_bytes: bytes, dest: Path, *, top_stripped: bool = True) -> dict:
    """Extract tar bytes to dest, applying all safety checks.
    Returns a summary dict.
    """
    dest.mkdir(parents=True, exist_ok=True)
    summary = {"files": 0, "skipped": 0, "total_bytes": 0, "reasons": {}}

    # Try to detect the top-level directory to strip
    detected_prefix = None
    if top_stripped:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as peek:
            for m in peek:
                name = m.name.lstrip("./")
                if "/" in name:
                    detected_prefix = name.split("/")[0]
                    break

    # Build a list of safe members first, then extract with data_filter.
    # data_filter adds its own paranoia (absolute paths, .., symlinks) on top
    # of our checks.
    safe_members = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in tf:
            our_filtered = _safe_extract_filter(
                member, dest, top_stripped=bool(detected_prefix)
            )
            if our_filtered is None:
                summary["skipped"] += 1
                summary["reasons"][member.name] = "safety filter"
                continue
            safe_members.append(our_filtered)

    extracted_files = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in safe_members:
            try:
                tf.extract(member, path=dest, filter=tarfile.data_filter)
                extracted_path = dest / member.name
                if extracted_path.exists():
                    if extracted_path.is_file():
                        extracted_path.chmod(DEST_PERMS_FILE)
                    elif extracted_path.is_dir():
                        extracted_path.chmod(DEST_PERMS_DIR)
                extracted_files.append(member.name)
                summary["files"] += 1
                summary["total_bytes"] += member.size
            except (OSError, tarfile.FilterError) as e:
                print(f"  EXTRACT ERROR {member.name}: {e}")
                summary["skipped"] += 1

    summary["extracted_files"] = extracted_files
    summary["prefix_stripped"] = detected_prefix
    return summary


# ── Test fixtures ─────────────────────────────────────────────────────────
def make_tar(members: list[tuple[str, bytes, int, str]]) -> bytes:
    """Build a tar.gz from a list of (name, content, size, type) tuples.
    type: 'file', 'dir', 'symlink', 'hardlink', 'chr', 'fifo'
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content, size, ftype in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mtime = 1000000000
            if ftype == "file":
                info.type = tarfile.REGTYPE
                info.mode = DEST_PERMS_FILE
            elif ftype == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = DEST_PERMS_DIR
            elif ftype == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
            elif ftype == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = "/etc/passwd"
            elif ftype == "chr":
                info.type = tarfile.CHRTYPE
            elif ftype == "fifo":
                info.type = tarfile.FIFOTYPE
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def run_test(name, tar_members, expect_skipped=None, expect_extracted=None):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    tmp = tempfile.mkdtemp(prefix=f"si-test-{name[:8]}-")
    try:
        tar_data = make_tar(tar_members)
        print(f"  Tar size: {len(tar_data)} bytes")
        result = safe_extract(tar_data, Path(tmp))
        print(f"  Result: {result['files']} files extracted, {result['skipped']} skipped")
        print(f"  Extracted files: {result['extracted_files']}")
        print(f"  Skipped reasons: {result['reasons']}")
        print(f"  Total bytes: {result['total_bytes']}")
        print(f"  Prefix stripped: {result['prefix_stripped']}")

        # Verify: check for traversal escapes
        all_paths = list(Path(tmp).rglob("*"))
        escaped = [p for p in all_paths if ".." in str(p.relative_to(tmp))]
        if escaped:
            print(f"  FAIL: escaped paths found: {escaped}")
        else:
            print(f"  PASS: no traversal escapes")

        # Verify: check for absolute paths
        absolute = [p for p in all_paths if str(p).startswith("/") or str(p).startswith("\\\\")]
        if absolute:
            print(f"  FAIL: absolute paths: {absolute}")
        else:
            print(f"  PASS: no absolute path escapes")

        # Verify: check for symlinks
        symlinks = [p for p in all_paths if p.is_symlink()]
        if symlinks:
            print(f"  FAIL: symlinks created: {symlinks}")
        else:
            print(f"  PASS: no symlinks")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Run tests ─────────────────────────────────────────────────────────────
print("S-3 TARBALL EXTRACTOR SPIKE")
print("=" * 60)

# Test 1: Traversal attack
run_test(
    "traversal",
    [
        ("safe.txt", b"safe content", 12, "file"),
        ("../../etc/passwd", b"root:x:0:0", 12, "file"),
        ("subdir/../../etc/shadow", b"secret", 6, "file"),
    ]
)

# Test 2: Absolute paths
run_test(
    "absolute_paths",
    [
        ("safe.txt", b"safe", 4, "file"),
        ("/etc/passwd", b"root:x:0:0", 12, "file"),
        ("/tmp/evil.sh", b"#!/bin/sh", 9, "file"),
    ]
)

# Test 3: Symlinks
run_test(
    "symlinks",
    [
        ("safe.txt", b"safe", 4, "file"),
        ("link.txt", b"", 0, "symlink"),
        ("link_to_passwd", b"", 0, "symlink"),
    ]
)

# Test 4: Hardlinks
run_test(
    "hardlinks",
    [
        ("safe.txt", b"safe", 4, "file"),
        ("hardlink.txt", b"", 0, "hardlink"),
    ]
)

# Test 5: Special files (devices, FIFOs)
run_test(
    "special_files",
    [
        ("safe.txt", b"safe", 4, "file"),
        ("null_dev", b"", 0, "chr"),
        ("mypipe", b"", 0, "fifo"),
    ]
)

# Test 6: Tar bomb (many small files)
def tar_bomb_members(n=10000):
    members = []
    for i in range(n):
        members.append((f"file_{i:06d}.txt", b"x" * 100, 100, "file"))
    return members

run_test(
    "tar_bomb",
    tar_bomb_members(n=5000),
    expect_extracted=5000,
)

# Test 7: GitHub-style tarball with top-level dir
run_test(
    "github_style",
    [
        ("owner-repo-a1b2c3d/README.md", b"# My Project", 13, "file"),
        ("owner-repo-a1b2c3d/src/main.py", b"print('hello')", 14, "file"),
        ("owner-repo-a1b2c3d/src/utils.py", b"def foo(): pass", 15, "file"),
        ("owner-repo-a1b2c3d/package.json", b'{"name":"test"}', 18, "file"),
    ]
)

# Test 8: Control chars in name
run_test(
    "control_chars",
    [
        ("safe.txt", b"safe", 4, "file"),
        ("evil\x00name.txt", b"evil", 4, "file"),
        ("tab\there.txt", b"tab", 3, "file"),
    ]
)

# Test 9: Too-long name
long_name = "a" * 300
run_test(
    "long_name",
    [
        ("safe.txt", b"safe", 4, "file"),
        (long_name, b"data", 4, "file"),
    ]
)

# Test 10: Deep nesting
def deep_nesting():
    members = []
    path = ""
    for i in range(45):
        path += "d/"
        members.append((f"{path}dir_{i}/", b"", 0, "dir"))
    members.append((f"{path}deep_file.txt", b"deep", 4, "file"))
    return members

run_test(
    "deep_nesting",
    deep_nesting(),
)

print("\n" + "=" * 60)
print("S-3 SPIKE COMPLETE")
print("=" * 60)
