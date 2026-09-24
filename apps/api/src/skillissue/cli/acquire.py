"""CLI: `python -m skillissue.cli.acquire <owner/repo>`.

Downloads a tarball, walks the tree, builds a manifest, and prints
a summary to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import TextIO

from skillissue.domain.url.exceptions import URLError
from skillissue.domain.url.models import RepoRef
from skillissue.domain.url.parser import parse
from skillissue.pipeline.acquire.downloader import download_tarball
from skillissue.pipeline.denylist import check_optout, check_denylist, is_denylisted
from skillissue.pipeline.filter.language import detect
from skillissue.pipeline.filter.loc import count_loc
from skillissue.pipeline.filter.manifest import build_manifest
from skillissue.pipeline.filter.walker import WalkResult, walk
from skillissue.pipeline.hygiene import check as check_hygiene


# =====================================================================
# Minimal manifest reader from tarball (no full extract needed)
# =====================================================================


def _read_tarball_manifests(
    tarball_bytes: bytes,
) -> tuple[list[str], list[str]]:
    """List filenames and lockfile names from an in-memory tarball.

    Returns (all_names, lockfile_names).
    """
    buf = io.BytesIO(tarball_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        members = tf.getmembers()

    all_names: list[str] = []
    lockfile_names: list[str] = []

    _LOCKFILE_SUFFIXES = (".lock", ".lockb")
    _LOCKFILE_BASENAMES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "bun.lock", "bun.lockb", "poetry.lock", "Pipfile.lock",
        "uv.lock", "pdm.lock", "cargo.lock", "go.sum",
        "gemfile.lock", "composer.lock", "mix.lock",
    }

    for m in members:
        name = m.name
        if m.isdir():
            continue
        # strip top-level dir (owner-repo-sha/)
        parts = name.split("/")
        if len(parts) <= 1:
            continue
        rel = "/".join(parts[1:])
        all_names.append(rel)
        bn = name.split("/")[-1].lower()
        if any(bn.endswith(s) for s in _LOCKFILE_SUFFIXES) or bn in _LOCKFILE_BASENAMES:
            lockfile_names.append(rel)

    return all_names, lockfile_names


# =====================================================================
# Coverage + stats
# =====================================================================

from skillissue.pipeline.coverage import CoverageKind, decide as decide_coverage


def _compute_stats(
    files: list,  # list of FileInfo
    manifest: list[dict],
) -> dict:
    loc_total = sum(f.loc for f in files)
    loc_analyzed = sum(f.loc for f in files)
    lang_counts: dict[str, int] = {}
    for f in files:
        lang_counts[f.lang] = lang_counts.get(f.lang, 0) + 1

    # Determine loc_supported: we count all recognized (non-"unknown") langs as supported
    loc_supported = sum(f.loc for f in files if f.lang != "unknown")

    coverage = decide_coverage(
        loc_total=loc_total,
        loc_supported=loc_supported,
        loc_analyzed=loc_analyzed,
        file_count=len(files),
    )

    languages = sorted(lang_counts.keys())
    return {
        "total_files": len(files),
        "total_loc": loc_total,
        "loc_analyzed": loc_analyzed,
        "loc_supported": loc_supported,
        "languages": languages,
        "coverage": coverage.value,
    }


# =====================================================================
# Main acquire command
# =====================================================================


def _run_acquire(repo_input: str, output: TextIO = sys.stdout) -> int:
    # Parse the repo reference
    try:
        repo_ref = parse(repo_input)
    except URLError as exc:
        print(f"error: invalid repo reference: {exc}", file=sys.stderr)
        return 2

    # Denylist check
    try:
        check_denylist(repo_ref)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    # Download tarball
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        print(f"Downloading {repo_ref.full_name}...", file=sys.stderr)
        try:
            tarball = download_tarball(
                repo_ref.owner, repo_ref.repo,
                sha="a" * 40,  # placeholder; use HEAD
                dest_dir=tmp,
            )
        except Exception as exc:
            print(f"error: download failed: {exc}", file=sys.stderr)
            return 4

        tarball_bytes = tarball.read_bytes()

        # Extract
        extract_dir = tmp / "src"
        extract_dir.mkdir(exist_ok=True)
        import tarfile as _tf
        try:
            with _tf.open(tarball, mode="r:gz") as tf:
                members = tf.getmembers()
                # Find the top-level directory
                top = None
                for m in members:
                    parts = m.name.split("/")
                    if len(parts) > 1 and parts[1] == "":
                        continue
                    if len(parts) >= 2:
                        top = parts[0]
                        break
                tf.extractall(path=extract_dir, members=[
                    m for m in members if top and m.name.startswith(top + "/")
                ])
        except Exception as exc:
            print(f"error: extraction failed: {exc}", file=sys.stderr)
            return 5

        # Determine the actual source dir
        src_children = list(extract_dir.iterdir())
        if len(src_children) == 1 and src_children[0].is_dir():
            src_dir = src_children[0]
        else:
            src_dir = extract_dir

        # Opt-out file check
        try:
            check_optout(repo_ref, src_dir)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3

        # Walk
        result = walk(src_dir)

        # Build manifest
        manifest = build_manifest(result.files)

        # Collect all file paths (including subdirectories) for hygiene
        all_paths = [f.path for f in result.files] + result.manifests

        # Hygiene
        hygiene_flags = check_hygiene(all_paths, src_dir)

        # Stats
        stats = _compute_stats(result.files, manifest)

        # Output summary
        summary = {
            "repo": repo_ref.full_name,
            "files": stats["total_files"],
            "loc": stats["total_loc"],
            "loc_analyzed": stats["loc_analyzed"],
            "loc_supported": stats["loc_supported"],
            "languages": stats["languages"],
            "coverage": stats["coverage"],
            "manifests": result.manifests,
            "hygiene_flags": hygiene_flags,
        }
        json.dump(summary, output, indent=2)
        output.write("\n")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="skillissue.cli.acquire",
        description="Acquire and analyze a GitHub repository.",
    )
    subparsers = parser.add_subparsers(dest="command")

    acquire_parser = subparsers.add_parser(
        "acquire", help="Download and analyze a GitHub repository."
    )
    acquire_parser.add_argument(
        "repo",
        help="GitHub repo URL or OWNER/REPO shorthand.",
    )

    args = parser.parse_args(argv)

    if args.command == "acquire":
        return _run_acquire(args.repo)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
