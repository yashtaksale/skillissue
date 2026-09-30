"""Tests for the tarball downloader."""
from __future__ import annotations

import asyncio
import io
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from skillissue.pipeline.acquire.downloader import (
    DownloadError,
    TarballTooLargeError,
    download_tarball,
)


def _make_tarball_gz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _FakeGetResponse:
    """Fake async HTTP response for the initial GET (redirect check)."""

    def __init__(self, *, status_code: int = 200, redirect_url: str | None = None):
        self.status_code = status_code
        self.headers = {}
        if redirect_url:
            self.headers["Location"] = redirect_url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "oops", request=None, response=self
            )


class _FakeStreamResponse:
    """Fake async HTTP response that streams bytes."""

    def __init__(self, payload: bytes, *, status_code: int = 200):
        self.status_code = status_code
        self.headers = {}
        self._payload = payload
        self._raise_error = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self._raise_error and self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "oops", request=None, response=self
            )

    async def aiter_bytes(self, chunk_size: int = 65536):
        offset = 0
        while offset < len(self._payload):
            yield self._payload[offset:offset + chunk_size]
            offset += chunk_size


class _FakeClient:
    """Fake httpx.AsyncClient that returns a stream response."""

    def __init__(
        self,
        get_response: _FakeGetResponse | None = None,
        stream_response: _FakeStreamResponse | None = None,
    ):
        self._get_response = get_response
        self._stream_response = stream_response
        self.get_called = False
        self.stream_called = False

    async def get(self, *args, **kwargs):
        self.get_called = True
        if self._get_response is None:
            raise ValueError("No GET response configured")
        # client.get() returns the response directly, not a context manager
        return self._get_response

    def stream(self, *args, **kwargs):
        # Real httpx returns an async context manager from `stream()`.
        self.stream_called = True
        if self._stream_response is None:
            raise ValueError("No stream response configured")
        return _FakeStreamCtx(self._stream_response)

    async def aclose(self) -> None:
        pass


class _FakeStreamCtx:
    """Async context manager returned by `_FakeClient.stream`."""

    def __init__(self, response: _FakeStreamResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_download_streams_tarball_to_disk(tmp_path: Path) -> None:
    payload = _make_tarball_gz({"README.md": b"hello world"})
    owner, repo, sha = "octocat", "Hello-World", "a" * 40

    # First GET returns redirect to codeload.github.com
    get_resp = _FakeGetResponse(
        status_code=302,
        redirect_url="https://codeload.github.com/octocat/Hello-World/tar.gz/a" * 40
    )
    stream_resp = _FakeStreamResponse(payload)
    client = _FakeClient(get_response=get_resp, stream_response=stream_resp)

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", return_value=client):
        result = await download_tarball(owner, repo, sha, tmp_path)

    assert result.exists()
    assert result.name == f"{owner}-{repo}-{sha[:7]}.tar.gz"
    assert result.read_bytes() == payload
    assert client.get_called
    assert client.stream_called


@pytest.mark.asyncio
async def test_download_sends_authorization_header(tmp_path: Path) -> None:
    payload = _make_tarball_gz({"a.txt": b"x"})

    get_resp = _FakeGetResponse(
        status_code=302,
        redirect_url="https://codeload.github.com/o/r/tar.gz/b" * 40
    )
    stream_resp = _FakeStreamResponse(payload)

    captured_kwargs: dict = {}

    def _capturing_client(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeClient(get_response=get_resp, stream_response=stream_resp)

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", side_effect=_capturing_client):
        await download_tarball("o", "r", "b" * 40, tmp_path, github_token="tok123")

    # The client is created with follow_redirects=False now
    assert "follow_redirects" in captured_kwargs
    assert captured_kwargs["follow_redirects"] is False


@pytest.mark.asyncio
async def test_download_rejects_oversize_streams(tmp_path: Path) -> None:
    owner, repo, sha = "o", "r", "c" * 40
    # Build a payload just over 150 MB
    large = b"\x00" * (151 * 1024 * 1024)

    get_resp = _FakeGetResponse(
        status_code=302,
        redirect_url="https://codeload.github.com/o/r/tar.gz/c" * 40
    )
    stream_resp = _FakeStreamResponse(large)
    client = _FakeClient(get_response=get_resp, stream_response=stream_resp)

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", return_value=client):
        with pytest.raises(TarballTooLargeError):
            await download_tarball(owner, repo, sha, tmp_path)

    # Partial files cleaned up
    assert not any(tmp_path.glob("*.tar.gz.part"))
    assert not any(tmp_path.glob("*.tar.gz"))


@pytest.mark.asyncio
async def test_download_retries_on_failure(tmp_path: Path) -> None:
    payload = _make_tarball_gz({"x": b"y"})
    call_count = 0

    def _make_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        get_resp = _FakeGetResponse(
            status_code=302,
            redirect_url=f"https://codeload.github.com/o/r/tar.gz/c{call_count}"
        )
        if call_count == 1:
            stream_resp = _FakeStreamResponse(b"", status_code=500)
            stream_resp._raise_error = True
            return _FakeClient(get_response=get_resp, stream_response=stream_resp)
        return _FakeClient(get_response=get_resp, stream_response=_FakeStreamResponse(payload))

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", side_effect=_make_client):
        result = await download_tarball("o", "r", "c" * 40, tmp_path)

    assert result.exists()


@pytest.mark.asyncio
async def test_download_gives_up_after_retries(tmp_path: Path) -> None:
    get_resp = _FakeGetResponse(
        status_code=302,
        redirect_url="https://codeload.github.com/o/r/tar.gz/c" * 40
    )
    stream_resp = _FakeStreamResponse(b"", status_code=500)
    stream_resp._raise_error = True
    client = _FakeClient(get_response=get_resp, stream_response=stream_resp)

    with patch(
        "skillissue.pipeline.acquire.downloader.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(DownloadError):
            await download_tarball("o", "r", "c" * 40, tmp_path, retries=1)


@pytest.mark.asyncio
async def test_download_rejects_unsafe_redirect(tmp_path: Path) -> None:
    """Test that redirects to non-codeload.github.com are rejected."""
    owner, repo, sha = "o", "r", "c" * 40

    # Redirect to unsafe URL
    get_resp = _FakeGetResponse(
        status_code=302,
        redirect_url="http://evil.com/malware.tar.gz"
    )
    client = _FakeClient(get_response=get_resp, stream_response=_FakeStreamResponse(b"x"))

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", return_value=client):
        with pytest.raises(DownloadError, match="Unsafe redirect"):
            await download_tarball(owner, repo, sha, tmp_path)


@pytest.mark.asyncio
async def test_download_handles_no_redirect(tmp_path: Path) -> None:
    """Test direct response without redirect."""
    payload = _make_tarball_gz({"direct.txt": b"data"})
    owner, repo, sha = "o", "r", "d" * 40

    # No redirect - direct 200
    get_resp = _FakeGetResponse(status_code=200)
    stream_resp = _FakeStreamResponse(payload)
    client = _FakeClient(get_response=get_resp, stream_response=stream_resp)

    with patch("skillissue.pipeline.acquire.downloader.httpx.AsyncClient", return_value=client):
        result = await download_tarball(owner, repo, sha, tmp_path)

    assert result.exists()
    assert result.read_bytes() == payload