"""Tarball downloader with streaming, size cap, and retry."""
from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path

import httpx

from skillissue.domain.url.exceptions import URLError


class DownloadError(URLError):
    """Raised when the tarball download fails after retries."""


class TarballTooLargeError(URLError):
    """Raised when the downloaded tarball exceeds the size cap."""


_MAX_TARBALL_BYTES = 150 * 1024 * 1024
_DOWNLOAD_TIMEOUT = 30
_MAX_RETRIES = 1
_USER_AGENT = "skillissue/0.1 (code health scanner)"
_TARBALL_CHUNK = 256 * 1024


async def download_tarball(
    owner: str,
    repo: str,
    sha: str,
    dest_dir: Path,
    *,
    github_token: str = "",
    retries: int = _MAX_RETRIES,
    _client: httpx.AsyncClient | None = None,
) -> Path:
    """Stream a GitHub tarball to *dest_dir*/{owner}-{repo}-{short_sha}.tar.gz.

    Args:
        owner: Repository owner.
        repo: Repository name.
        sha: Full 40-char commit SHA.
        dest_dir: Directory to write the tarball into.
        github_token: Optional GitHub token for higher rate limits.
        retries: Number of retry attempts after the first failure.
        _client: Optional pre-built client for testing.

    Returns:
        Path to the downloaded tarball.

    Raises:
        TarballTooLargeError: If streamed content exceeds 150 MB.
        DownloadError: If download fails after all retries.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    short_sha = sha[:7]
    filename = f"{owner}-{repo}-{short_sha}.tar.gz"
    dest_path = dest_dir / filename
    dest_path.unlink(missing_ok=True)

    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{sha}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    last_error: Exception | None = None

    for attempt in range(1 + retries):
        tmp_fh, tmp_path_str = tempfile.mkstemp(
            dir=str(dest_dir), suffix=".tar.gz.part"
        )
        os.close(tmp_fh)
        tmp_path = Path(tmp_path_str)

        if _client is None:
            client = httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(
                    _DOWNLOAD_TIMEOUT, connect=10, write=_DOWNLOAD_TIMEOUT
                ),
            )
            owns_client = True
        else:
            client = _client
            owns_client = False

        try:
            # First request to get the redirect URL without following it automatically
            resp = await client.get(url, headers=headers)
            if resp.status_code in (301, 302, 307, 308):
                redirect_url = resp.headers.get("Location")
                if not redirect_url:
                    raise DownloadError("Redirect missing Location header")
                
                # Enforce safe domain for redirect (mitigate SSRF)
                if not redirect_url.startswith("https://codeload.github.com/"):
                    raise DownloadError(f"Unsafe redirect target: {redirect_url}")
                
                # Use the safe redirect URL
                target_url = redirect_url
            else:
                resp.raise_for_status()
                target_url = url

            async with client.stream("GET", target_url, headers=headers) as response:
                response.raise_for_status()

                sha256 = hashlib.sha256()
                written = 0
                with open(tmp_path, "wb") as fh:
                    async for chunk in response.aiter_bytes(_TARBALL_CHUNK):
                        sha256.update(chunk)
                        written += len(chunk)
                        if written > _MAX_TARBALL_BYTES:
                            raise TarballTooLargeError(
                                f"Tarball exceeded "
                                f"{_MAX_TARBALL_BYTES // (1024 * 1024)} MB limit "
                                f"({written // (1024 * 1024)} MB received)"
                            )
                        fh.write(chunk)

            tmp_path.rename(dest_path)
            if owns_client:
                await client.aclose()
            return dest_path

        except TarballTooLargeError:
            tmp_path.unlink(missing_ok=True)
            dest_path.unlink(missing_ok=True)
            if owns_client:
                await client.aclose()
            raise

        except Exception as exc:
            last_error = exc
            tmp_path.unlink(missing_ok=True)
            if owns_client:
                await client.aclose()
            if attempt < retries:
                await asyncio.sleep(min(2 ** attempt, 8))

    raise DownloadError(
        f"Failed to download tarball from {url} after {1 + retries} attempts: {last_error}"
    )
