"""GitHub repo URL parser.

Accepts:
- https://github.com/owner/repo
- https://www.github.com/owner/repo
- http://github.com/owner/repo
- Optional .git suffix
- Optional /tree/{branch} (branch captured as ref; path beyond branch ignored)
- Optional trailing slash, query, fragment
- Shorthand: owner/repo

Rejects: non-github hosts, credentials, non-http(s) schemes,
         control characters, unsafe names, length > 300.
"""
from __future__ import annotations

import re
import urllib.parse

from skillissue.domain.url.exceptions import (
    ControlCharacterError,
    InvalidFormatError,
    ReservedNameError,
    TooLongError,
    UnsupportedHostError,
    URLError,
)
from skillissue.domain.url.models import RepoRef

_MAX_INPUT_LENGTH = 300

_FULL_URL_RE = re.compile(
    r"^(?P<scheme>https?)://"
    r"(?:(?P<creds>[^@]+@))?"
    r"(?:www\.)?"
    r"github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)"
    r"/"
    r"(?P<repo>[A-Za-z0-9_.-]{1,100})"
    r"(?P<git_suffix>\.git)?"
    r"(?:/(?:tree|blob)/(?P<ref>[^?#]+))?"
    r"(?:/.*)?"
    r"/?"
    r"(?:[?#].*)?$"
)

_SHORTHAND_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[A-Za-z0-9_.-]{1,100})$"
)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _check_length(raw: str) -> None:
    if len(raw) > _MAX_INPUT_LENGTH:
        raise TooLongError(
            f"Input exceeds {_MAX_INPUT_LENGTH} characters (got {len(raw)})"
        )


def _check_control_chars(raw: str) -> None:
    if _CONTROL_CHARS_RE.search(raw):
        raise ControlCharacterError("Input contains control characters")


def _check_scheme(scheme: str | None) -> None:
    if scheme is not None and scheme not in ("http", "https"):
        raise InvalidFormatError(
            f"Unsupported scheme '{scheme}'; only http(s) is allowed"
        )


def _check_host(host: str | None) -> None:
    if host is None:
        return
    if host.lower() != "github.com":
        raise UnsupportedHostError(
            f"Only github.com is supported, got '{host}'"
        )


def _check_credentials(creds: str | None) -> None:
    if creds is not None:
        raise InvalidFormatError(
            "Embedded credentials (user:pass@) are not allowed"
        )


def _normalize_owner(owner: str) -> str:
    return owner.lower()


def _normalize_repo(repo: str) -> str:
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo


def _validate_names(owner: str, repo: str) -> None:
    if owner.startswith("-") or owner.endswith("-"):
        raise ReservedNameError("Owner name cannot start or end with '-'")
    if repo in (".", ".."):
        raise ReservedNameError(f"Repository name '{repo}' is reserved")


def parse(raw: str) -> RepoRef:
    """Parse a GitHub repo reference from a URL or shorthand.

    Args:
        raw: A URL (https://github.com/owner/repo[/tree/branch]) or
             shorthand (owner/repo).

    Returns:
        RepoRef with normalized owner, repo, and optional ref.

    Raises:
        TooLongError: input exceeds 300 characters.
        ControlCharacterError: input contains C0/DEL control chars.
        InvalidFormatError: malformed URL, unsupported scheme, credentials.
        UnsupportedHostError: host is not github.com.
        UnsafeRepoError: owner/repo fail validation.
        ReservedNameError: owner starts/ends with '-' or repo is '.'/'..'.
        URLError: base class for all parse failures.
    """
    if not isinstance(raw, str):
        raise InvalidFormatError("Input must be a string")

    # Stage 1: structural checks (before strip, so trailing control chars are caught)
    _check_length(raw)
    _check_control_chars(raw)

    raw = raw.strip()

    # Stage 2: try full URL
    full_match = _FULL_URL_RE.match(raw)
    if full_match:
        scheme = full_match.group("scheme")
        creds = full_match.group("creds")
        owner_raw = full_match.group("owner")
        repo_raw = full_match.group("repo")
        ref_raw = full_match.group("ref")
        ref = ref_raw.rstrip("/") if ref_raw else None

        _check_scheme(scheme)
        _check_host("github.com")
        _check_credentials(creds)

        owner = _normalize_owner(owner_raw)
        repo = _normalize_repo(repo_raw)
        _validate_names(owner, repo)
        return RepoRef(owner=owner, repo=repo, ref=ref)

    # Stage 3: try shorthand
    shorthand_match = _SHORTHAND_RE.match(raw)
    if shorthand_match:
        owner_raw = shorthand_match.group("owner")
        repo_raw = shorthand_match.group("repo")

        # Reject .git suffix in shorthand (full URL handles it, shorthand shouldn't)
        if repo_raw.endswith(".git"):
            raise InvalidFormatError(
                ".git suffix is not allowed in shorthand (use the full URL form)"
            )

        owner = _normalize_owner(owner_raw)
        repo = _normalize_repo(repo_raw)
        _validate_names(owner, repo)
        return RepoRef(owner=owner, repo=repo, ref=None)

    # Stage 4: determine specific failure
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        raise InvalidFormatError(
            f"Unsupported scheme '{parsed.scheme}'; only http(s) is allowed"
        )

    host = parsed.hostname
    if host and host.lower() != "github.com":
        raise UnsupportedHostError(
            f"Only github.com is supported, got '{host}'"
        )

    if parsed.username or parsed.password:
        raise InvalidFormatError(
            "Embedded credentials (user:pass@) are not allowed"
        )

    raise InvalidFormatError(
        "Input does not match a recognized GitHub repo URL or shorthand "
        "(expected https://github.com/owner/repo or owner/repo)"
    )
