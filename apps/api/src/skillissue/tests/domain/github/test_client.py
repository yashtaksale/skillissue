"""Table-driven tests and hypothesis properties for the GitHub client.

Tests cover: ETag caching, error mapping, header construction,
cache key generation, and RepoMetadata validation.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import respx
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from skillissue.domain.github.client import (
    _base_headers,
    _cache_key,
    _check_status,
    _fetch_commit_sha,
    _fetch_metadata,
    _raise_rate_limit,
    _store_cache,
    resolve,
)
from skillissue.domain.github.exceptions import (
    AuthenticationError,
    EmptyRepoError,
    GitHubAPIError,
    RateLimitError,
    RepoNotFoundError,
)
from skillissue.domain.github.models import RepoMetadata
from skillissue.domain.url.models import RepoRef


# =====================================================================
# Helpers
# =====================================================================


def _make_redis(data: dict | None = None) -> MagicMock:
    """Create a mock async Redis client with optional initial data."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=json.dumps(data) if data else None)
    redis.setex = AsyncMock(return_value=True)
    return redis


def _github_response(
    status: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    else:
        resp.json = MagicMock(side_effect=ValueError("no json"))
    resp.headers = headers or {}
    resp.text = text
    return resp


# =====================================================================
# RepoMetadata
# =====================================================================


class TestRepoMetadata:
    def test_exceeds_size_limit_true(self):
        m = RepoMetadata(
            full_name="o/r",
            default_branch="main",
            size_kb=200 * 1024,
            is_fork=False,
            is_archived=False,
            stargazers_count=10,
            language="Python",
            commit_sha="abc123",
            etag='"abc"',
        )
        assert m.exceeds_size_limit(150) is True

    def test_exceeds_size_limit_false(self):
        m = RepoMetadata(
            full_name="o/r",
            default_branch="main",
            size_kb=50 * 1024,
            is_fork=False,
            is_archived=False,
            stargazers_count=10,
            language="Python",
            commit_sha="abc123",
            etag='"abc"',
        )
        assert m.exceeds_size_limit(150) is False

    def test_exceeds_at_boundary(self):
        m = RepoMetadata(
            full_name="o/r",
            default_branch="main",
            size_kb=150 * 1024,
            is_fork=False,
            is_archived=False,
            stargazers_count=0,
            language=None,
            commit_sha="abc",
            etag='""',
        )
        assert m.exceeds_size_limit(150) is False


# =====================================================================
# Cache key generation
# =====================================================================


class TestCacheKey:
    @pytest.mark.parametrize(
        "owner,repo,expected",
        [
            ("octocat", "Hello-World", "github:meta:octocat/hello-world"),
            ("OCtoCat", "Repo", "github:meta:octocat/repo"),
            ("my-org", "my-repo", "github:meta:my-org/my-repo"),
            ("A", "B", "github:meta:a/b"),
        ],
        ids=["standard", "mixed-case", "hyphens", "single-char"],
    )
    def test_cache_key_lowercased(self, owner, repo, expected):
        ref = RepoRef(owner=owner, repo=repo)
        key = _cache_key(ref)
        assert key == expected


# =====================================================================
# _check_status error mapping
# =====================================================================


class TestCheckStatus:
    def test_200_ok(self):
        resp = _github_response(200)
        _check_status(resp)

    def test_304_ok(self):
        resp = _github_response(304)
        _check_status(resp)

    def test_404_raises_not_found(self):
        resp = _github_response(404, text="Not Found")
        with pytest.raises(RepoNotFoundError, match="not found or not public"):
            _check_status(resp)

    def test_401_raises_auth(self):
        resp = _github_response(401, text="Bad credentials")
        with pytest.raises(AuthenticationError, match="authentication failed"):
            _check_status(resp)

    def test_403_raises_rate_limit(self):
        resp = _github_response(
            403,
            headers={"X-RateLimit-Reset": "1234567890"},
            text="rate limit",
        )
        with pytest.raises(RateLimitError, match="rate limit exceeded"):
            _check_status(resp)

    def test_409_raises_empty_repo(self):
        resp = _github_response(409, text="Git Repository is empty")
        with pytest.raises(EmptyRepoError, match="no commits"):
            _check_status(resp)

    def test_500_raises_generic(self):
        resp = _github_response(500, text="Internal Server Error")
        with pytest.raises(GitHubAPIError, match="unexpected status 500"):
            _check_status(resp)


# =====================================================================
# _raise_rate_limit
# =====================================================================


class TestRaiseRateLimit:
    def test_parses_reset_timestamp(self):
        resp = _github_response(
            403, headers={"X-RateLimit-Reset": "1700000000"}
        )
        with pytest.raises(RateLimitError) as exc_info:
            _raise_rate_limit(resp)
        assert exc_info.value.reset_at != ""

    def test_missing_header(self):
        resp = _github_response(403, headers={})
        with pytest.raises(RateLimitError):
            _raise_rate_limit(resp)

    def test_reset_at_formatted(self):
        resp = _github_response(
            403, headers={"X-RateLimit-Reset": "1700000000"}
        )
        with pytest.raises(RateLimitError) as exc_info:
            _raise_rate_limit(resp)
        assert "2023-11-14" in exc_info.value.reset_at


# =====================================================================
# ETag caching
# =====================================================================


class TestCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_metadata(self):
        cached_data = {
            "full_name": "octocat/hello-world",
            "default_branch": "main",
            "size_kb": 100,
            "is_fork": False,
            "is_archived": False,
            "stargazers_count": 500,
            "language": "Python",
            "commit_sha": "cached_sha",
            "etag": '"abc123"',
        }
        redis = _make_redis(cached_data)

        ref = RepoRef(owner="octocat", repo="Hello-World")
        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get(
                "https://api.github.com/repos/octocat/hello-world/commits/main"
            ).respond(200, text='"fresh_sha"')
            result = await resolve(
                ref, redis=redis, github_token="fake-token"
            )

        assert result.full_name == "octocat/hello-world"
        assert result.default_branch == "main"
        redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_metadata_api_call_on_cache_hit(self):
        """On cache hit, the metadata endpoint is not called.
        The commit SHA endpoint IS still called (always fresh)."""
        cached_data = {
            "full_name": "o/r",
            "default_branch": "main",
            "size_kb": 50,
            "is_fork": False,
            "is_archived": False,
            "stargazers_count": 1,
            "language": "Go",
            "commit_sha": "cached_sha",
            "etag": '"xyz"',
        }
        redis = _make_redis(cached_data)

        ref = RepoRef(owner="o", repo="r")
        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(200)
            mock_route.get(
                "https://api.github.com/repos/o/r/commits/main"
            ).respond(200, text='"fresh_sha"')
            result = await resolve(
                ref, redis=redis, github_token="fake-token"
            )

        # Metadata endpoint should NOT be called (cached)
        metadata_calls = [
            c for c in mock_route.calls
            if "/repos/o/r" in str(c.request.url)
            and "/commits" not in str(c.request.url)
        ]
        assert len(metadata_calls) == 0
        # But commit SHA endpoint IS called (always fresh)
        assert result.commit_sha == "fresh_sha"


# =====================================================================
# Cache miss (fetch + store)
# =====================================================================


class TestCacheMiss:
    @pytest.mark.asyncio
    async def test_fetches_and_caches_on_miss(self):
        redis = _make_redis()
        ref = RepoRef(owner="octocat", repo="Hello-World")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/octocat/hello-world").respond(
                200,
                json={
                    "full_name": "octocat/Hello-World",
                    "default_branch": "main",
                    "size": 100,
                    "fork": False,
                    "archived": False,
                    "stargazers_count": 500,
                    "language": "Python",
                },
                headers={"ETag": '"meta123"'},
            )
            mock_route.get(
                "https://api.github.com/repos/octocat/hello-world/commits/main"
            ).respond(200, text='"sha_abc123"')

            result = await resolve(
                ref, redis=redis, github_token="fake-token"
            )

        assert result.full_name == "octocat/Hello-World"
        assert result.commit_sha == "sha_abc123"
        redis.setex.assert_called_once()
        cache_key_arg = redis.setex.call_args[0][0]
        assert "github:meta:octocat/hello-world" in cache_key_arg

    @pytest.mark.asyncio
    async def test_stores_etag_in_cache(self):
        redis = _make_redis()
        ref = RepoRef(owner="o", repo="r")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(
                200,
                json={
                    "full_name": "o/r",
                    "default_branch": "main",
                    "size": 50,
                    "fork": False,
                    "archived": False,
                    "stargazers_count": 0,
                    "language": None,
                },
                headers={"ETag": '"myetag42"'},
            )
            mock_route.get(
                "https://api.github.com/repos/o/r/commits/main"
            ).respond(200, text='"sha42"')

            await resolve(ref, redis=redis, github_token="fake-token")

        setex_call = redis.setex.call_args
        cached_value = json.loads(setex_call[0][2])
        assert cached_value["etag"] == '"myetag42"'


# =====================================================================
# Error mapping
# =====================================================================


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_404_raises_not_found(self):
        redis = _make_redis()
        ref = RepoRef(owner="nonexistent", repo="repo")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/nonexistent/repo").respond(
                404, text="Not Found"
            )
            with pytest.raises(RepoNotFoundError):
                await resolve(ref, redis=redis, github_token="fake-token")

    @pytest.mark.asyncio
    async def test_403_rate_limit(self):
        redis = _make_redis()
        ref = RepoRef(owner="o", repo="r")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(
                403,
                headers={"X-RateLimit-Reset": "1700000000"},
                text="rate limit",
            )
            with pytest.raises(RateLimitError) as exc_info:
                await resolve(ref, redis=redis, github_token="fake-token")
        assert exc_info.value.reset_at != ""

    @pytest.mark.asyncio
    async def test_401_auth_error(self):
        redis = _make_redis()
        ref = RepoRef(owner="o", repo="r")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(
                401, text="Bad credentials"
            )
            with pytest.raises(AuthenticationError, match="authentication failed"):
                await resolve(ref, redis=redis, github_token="bad-token")

    @pytest.mark.asyncio
    async def test_409_empty_repo(self):
        redis = _make_redis()
        ref = RepoRef(owner="o", repo="r")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(
                200,
                json={
                    "full_name": "o/r",
                    "default_branch": "main",
                    "size": 0,
                    "fork": False,
                    "archived": False,
                    "stargazers_count": 0,
                    "language": None,
                },
                headers={"ETag": '"x"'},
            )
            mock_route.get(
                "https://api.github.com/repos/o/r/commits/main"
            ).respond(409, text="Git Repository is empty")
            with pytest.raises(EmptyRepoError, match="empty"):
                await resolve(ref, redis=redis, github_token="fake-token")

    @pytest.mark.asyncio
    async def test_500_generic_error(self):
        redis = _make_redis()
        ref = RepoRef(owner="o", repo="r")

        with respx.mock(assert_all_called=False) as mock_route:
            mock_route.get("https://api.github.com/repos/o/r").respond(
                500, text="Internal Server Error"
            )
            with pytest.raises(GitHubAPIError, match="unexpected status 500"):
                await resolve(ref, redis=redis, github_token="fake-token")


# =====================================================================
# Header construction
# =====================================================================


class TestHeaders:
    def test_authorization_header(self):
        headers = _base_headers("ghp_abc123")
        assert headers["Authorization"] == "Bearer ghp_abc123"

    def test_api_version_header(self):
        headers = _base_headers("token")
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_user_agent(self):
        headers = _base_headers("token")
        assert headers["User-Agent"] == "skillissue/0.1"


# =====================================================================
# Hypothesis property tests
# =====================================================================


class TestHypothesisProperties:
    @given(
        owner=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=39,
        ),
        repo=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=100,
        ),
    )
    @settings(max_examples=100, deadline=5000)
    def test_cache_key_always_lowercased(self, owner: str, repo: str):
        owner = "".join(c for c in owner if c.isalnum() or c == "-")
        repo = "".join(c for c in repo if c.isalnum() or c == "-")
        if not owner or not repo:
            assume(False)
        if owner.startswith("-") or owner.endswith("-"):
            assume(False)

        ref = RepoRef(owner=owner, repo=repo)
        key = _cache_key(ref)
        assert key == "github:meta:" + owner.lower() + "/" + repo.lower()

    @given(
        size_kb=st.integers(min_value=0, max_value=10_000_000),
        max_mb=st.integers(min_value=1, max_value=10_000),
    )
    @settings(max_examples=200, deadline=5000)
    def test_exceeds_size_limit_consistent(self, size_kb: int, max_mb: int):
        metadata = RepoMetadata(
            full_name="o/r",
            default_branch="main",
            size_kb=size_kb,
            is_fork=False,
            is_archived=False,
            stargazers_count=0,
            language=None,
            commit_sha="abc",
            etag='""',
        )
        expected = size_kb > max_mb * 1024
        assert metadata.exceeds_size_limit(max_mb) == expected
