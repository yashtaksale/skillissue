"""CLI: `python -m skillissue.cli.acquire acquire <owner/repo>`.

Downloads a tarball via the GitHub API, extracts it safely, walks the tree,
and prints a JSON summary to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
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
from skillissue.pipeline.denylist import check_denylist, check_optout
from skillissue.pipeline.filter.language import detect
from skillissue.pipeline.filter.loc import count_loc
from skillissue.pipeline.filter.manifest import build_manifest
from skillissue.pipeline.filter.walker import WalkResult, walk
from skillissue.pipeline.hygiene import check as check_hygiene


# =====================================================================
# Manifest reader from tarball on disk
# =====================================================================

_LOCKFILE_SUFFIXES = (".lock", ".lockb")
_LOCKFILE_BASENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb", "poetry.lock", "Pipfile.lock",
    "uv.lock", "pdm.lock", "cargo.lock", "go.sum",
    "gemfile.lock", "composer.lock", "mix.lock",
}


def _read_tarball_manifests(
    tarball_path: Path,
) -> tuple[list[str], list[str]]:
    """List filenames and lockfile names from a tarball on disk.

    Returns (all_names, lockfile_names), both with the top-level dir stripped.
    """
    with tarfile.open(tarball_path, mode="r:gz") as tf:
        members = tf.getmembers()

    all_names: list[str] = []
    lockfile_names: list[str] = []

    for m in members:
        if m.isdir():
            continue
        parts = m.name.split("/")
        if len(parts) <= 1:
            continue
        rel = "/".join(parts[1:])
        all_names.append(rel)
        bn = parts[-1].lower()
        if any(bn.endswith(s) for s in _LOCKFILE_SUFFIXES) or bn in _LOCKFILE_BASENAMES:
            lockfile_names.append(rel)

    return all_names, lockfile_names


# =====================================================================
# Stats
# =====================================================================

from skillissue.pipeline.coverage import decide as decide_coverage


def _compute_stats(files: list) -> dict:
    loc_total = sum(f.loc for f in files)
    lang_counts: dict[str, int] = {}
    for f in files:
        lang_counts[f.lang] = lang_counts.get(f.lang, 0) + 1

    coverage = decide_coverage(
        loc_total=loc_total,
        loc_supported=loc_total,
        loc_analyzed=loc_total,
        file_count=len(files),
    )

    return {
        "total_files": len(files),
        "total_loc": loc_total,
        "languages": sorted(lang_counts.keys()),
        "coverage": coverage.value,
    }


# =====================================================================
# CLI entry point (sync wrapper around async core)
# =====================================================================


def _run_acquire(repo_input: str, output: TextIO = sys.stdout) -> int:
    """Parse a repo URL, download its tarball, and print a JSON summary."""
    try:
        repo_ref = parse(repo_input)
    except URLError as exc:
        print(f"error: invalid repo reference: {exc}", file=sys.stderr)
        return 2

    try:
        check_denylist(repo_ref)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    github_token = os.environ.get("GITHUB_TOKEN", "")

    try:
        summary = asyncio.run(_acquire_async(repo_ref, github_token))
    except URLError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"error: unexpected: {exc}", file=sys.stderr)
        return 5

    json.dump(summary, output, indent=2)
    output.write("\n")
    return 0


async def _acquire_async(repo_ref: RepoRef, github_token: str) -> dict:
    """Async core: download tarball, extract, walk, analyze."""
    import httpx
    from skillissue.pipeline.acquire.extractor import safe_extract

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        print(f"Downloading {repo_ref.full_name}...", file=sys.stderr)

        # 1. Fetch the default branch SHA for a reproducible tarball.
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30, connect=10),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "skillissue/0.1",
            },
        ) as client:
            if github_token:
                client.headers["Authorization"] = f"Bearer {github_token}"
            resp = await client.get(
                f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}"
            )
            resp.raise_for_status()
            meta = resp.json()
            default_branch = meta.get("default_branch", "main")
            head_resp = await client.get(
                f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}"
                f"/git/ref/heads/{default_branch}"
            )
            head_resp.raise_for_status()
            sha = head_resp.json()["object"]["sha"]

        # 2. Download tarball (streamed to disk, 150 MB cap, 1 retry).
        from skillissue.pipeline.acquire.downloader import download_tarball
        tarball_path = await download_tarball(
            repo_ref.owner, repo_ref.repo,
            sha=sha, dest_dir=tmp, github_token=github_token,
        )
        print(f"Downloaded {tarball_path.stat().st_size // 1024} KB", file=sys.stderr)

        # 3. Read manifests before extraction.
        _, lockfile_names = _read_tarball_manifests(tarball_path)

        # 4. Safe extraction with traversal/symlink/size/depth guards.
        extract_dir = tmp / "src"
        extract_dir.mkdir(exist_ok=True)
        safe_extract(tarball_path, extract_dir)

        # 5. Determine actual source dir (strip top-level dir).
        src_children = sorted(extract_dir.iterdir())
        if len(src_children) == 1 and src_children[0].is_dir():
            src_dir = src_children[0]
        else:
            src_dir = extract_dir

        # 6. Opt-out check.
        try:
            check_optout(repo_ref, src_dir)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise URLError(str(exc))

        # 7. Walk the tree.
        result: WalkResult = walk(src_dir)

        # 8. Build manifest.
        build_manifest(result.files)

        # 9. Hygiene.
        all_paths = [f.path for f in result.files] + result.manifests
        hygiene_flags = check_hygiene(all_paths, src_dir)

        # 10. Stats.
        stats = _compute_stats(result.files)

        return {
            "repo": repo_ref.full_name,
            "ref": default_branch,
            "commit_sha": sha[:12],
            "files": stats["total_files"],
            "loc": stats["total_loc"],
            "languages": stats["languages"],
            "coverage": stats["coverage"],
            "manifests": lockfile_names,
            "hygiene_flags": hygiene_flags,
        }


# =====================================================================
# CLI entry point
# =====================================================================


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="skillissue-cli",
        description="SkillIssue — code health scanner (acquire phase).",
    )
    subparsers = parser.add_subparsers(dest="command")

    acquire_parser = subparsers.add_parser(
        "acquire", help="Download and profile a GitHub repository."
    )
    acquire_parser.add_argument(
        "repo",
        help="GitHub repo URL or OWNER/REPO shorthand (e.g. octocat/Hello-World).",
    )

    args = parser.parse_args(argv)

    if args.command == "acquire":
        return _run_acquire(args.repo)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
