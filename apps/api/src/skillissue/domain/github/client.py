"""GitHub API client with ETag caching in Redis.

Resolves a RepoRef to commit SHA and caches repo metadata
to minimize API calls.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
from redis.asyncio import Redis

from skillissue.domain.github.exceptions import (
    AuthenticationError,
    EmptyRepoError,
    GitHubAPIError,
    RateLimitError,
    RepoNotFoundError,
)
from skillissue.domain.github.models import RepoMetadata
from skillissue.domain.url.models import RepoRef

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600
_CACHE_PREFIX = "github:meta:"
_API_BASE = "https://api.github.com"
_METADATA_TIMEOUT = 10.0
_COMMIT_TIMEOUT = 10.0


async def resolve(
    repo_ref: RepoRef,
    *,
    redis: Redis,
    github_token: str,
    ttl: int = _CACHE_TTL_SECONDS,
) -> RepoMetadata:
    """Resolve repo metadata for a RepoRef.

    Returns cached metadata if fresh, otherwise fetches from GitHub
    (with ETag conditional request) and stores in Redis.

    Args:
        repo_ref: Parsed repo reference.
        redis: Async Redis client for caching.
        github_token: GitHub server token (PAT).
        ttl: Cache TTL in seconds (default 600 = 10 min).

    Returns:
        RepoMetadata with commit SHA populated.

    Raises:
        RepoNotFoundError: repo does not exist or is private.
        RateLimitError: GitHub rate limit exhausted.
        EmptyRepoError: repo has no commits.
        AuthenticationError: token is invalid.
        GitHubAPIError: any other API failure.
    """
    cache_key = _cache_key(repo_ref)

    # Try cache first
    cached = await redis.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        metadata = RepoMetadata(
            full_name=data["full_name"],
            default_branch=data["default_branch"],
            size_kb=data["size_kb"],
            is_fork=data["is_fork"],
            is_archived=data["is_archived"],
            stargazers_count=data["stargazers_count"],
            language=data.get("language"),
            commit_sha=data["commit_sha"],
            etag=data["etag"],
        )
        logger.debug("cache_hit owner=%s repo=%s", repo_ref.owner, repo_ref.repo)
    else:
        metadata = await _fetch_metadata(repo_ref, github_token)
        await _store_cache(redis, cache_key, metadata, ttl)
        logger.debug("cache_miss fetch owner=%s repo=%s", repo_ref.owner, repo_ref.repo)

    # Resolve commit SHA (always fresh; short-lived and cheap)
    sha = await _fetch_commit_sha(repo_ref, metadata.default_branch, github_token)
    return RepoMetadata(
        full_name=metadata.full_name,
        default_branch=metadata.default_branch,
        size_kb=metadata.size_kb,
        is_fork=metadata.is_fork,
        is_archived=metadata.is_archived,
        stargazers_count=metadata.stargazers_count,
        language=metadata.language,
        commit_sha=sha,
        etag=metadata.etag,
    )


def _cache_key(repo_ref: RepoRef) -> str:
    return _CACHE_PREFIX + repo_ref.owner.lower() + "/" + repo_ref.repo.lower()


async def _fetch_metadata(repo_ref: RepoRef, token: str) -> RepoMetadata:
    owner_lc = repo_ref.owner.lower()
    repo_lc = repo_ref.repo.lower()
    url = _API_BASE + "/repos/" + owner_lc + "/" + repo_lc

    headers = _base_headers(token)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=_METADATA_TIMEOUT)
        except httpx.TransportError as exc:
            raise GitHubAPIError("GitHub API unreachable: " + str(exc)) from exc

    if resp.status_code == 304:
        raise GitHubAPIError("Got 304 with no cached metadata")
    _check_status(resp)

    data = resp.json()
    etag = resp.headers.get("ETag", "")

    return RepoMetadata(
        full_name=data["full_name"],
        default_branch=data["default_branch"],
        size_kb=data.get("size", 0),
        is_fork=data.get("fork", False),
        is_archived=data.get("archived", False),
        stargazers_count=data.get("stargazers_count", 0),
        language=data.get("language"),
        commit_sha="",
        etag=etag,
    )


async def _fetch_commit_sha(repo_ref: RepoRef, branch: str, token: str) -> str:
    owner_lc = repo_ref.owner.lower()
    repo_lc = repo_ref.repo.lower()
    url = (
        _API_BASE + "/repos/" + owner_lc + "/" + repo_lc + "/commits/" + branch
    )
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github.sha",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=_COMMIT_TIMEOUT)
        except httpx.TransportError as exc:
            raise GitHubAPIError("GitHub API unreachable: " + str(exc)) from exc

    if resp.status_code == 409:
        raise EmptyRepoError(
            "Repository " + repo_ref.full_name + " is empty (no commits)"
        )
    if resp.status_code == 404:
        raise RepoNotFoundError(
            "Repository " + repo_ref.full_name + " not found or not public"
        )
    if resp.status_code == 401:
        raise AuthenticationError("GitHub token is invalid or expired")
    if resp.status_code == 403:
        _raise_rate_limit(resp)
    if resp.status_code != 200:
        raise GitHubAPIError(
            "GitHub API error " + str(resp.status_code) + ": " + resp.text[:200]
        )

    return resp.text.strip('"')


async def _store_cache(redis: Redis, key: str, metadata: RepoMetadata, ttl: int) -> None:
    payload = {
        "full_name": metadata.full_name,
        "default_branch": metadata.default_branch,
        "size_kb": metadata.size_kb,
        "is_fork": metadata.is_fork,
        "is_archived": metadata.is_archived,
        "stargazers_count": metadata.stargazers_count,
        "language": metadata.language,
        "commit_sha": metadata.commit_sha,
        "etag": metadata.etag,
    }
    await redis.setex(key, ttl, json.dumps(payload))


def _base_headers(token: str) -> dict:
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "skillissue/0.1",
    }


def _check_status(resp: httpx.Response) -> None:
    if resp.status_code == 304:
        return
    if resp.status_code == 200:
        return
    if resp.status_code == 404:
        raise RepoNotFoundError(
            "Repository not found or not public (HTTP " + str(resp.status_code) + ")"
        )
    if resp.status_code == 401:
        raise AuthenticationError("GitHub authentication failed -- check token")
    if resp.status_code == 403:
        _raise_rate_limit(resp)
    if resp.status_code == 409:
        raise EmptyRepoError("Repository has no commits (empty repo)")
    raise GitHubAPIError(
        "GitHub API unexpected status " + str(resp.status_code) + ": " + resp.text[:300]
    )


def _raise_rate_limit(resp: httpx.Response) -> None:
    reset_ts = resp.headers.get("X-RateLimit-Reset", "")
    reset_at = ""
    if reset_ts:
        try:
            dt = datetime.fromtimestamp(int(resp.headers.get("X-RateLimit-Reset", "0")), tz=timezone.utc)
            reset_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            reset_at = str(reset_ts)
    raise RateLimitError(
        "GitHub rate limit exceeded (reset at " + reset_at + ")",
        reset_at=reset_at,
    )
