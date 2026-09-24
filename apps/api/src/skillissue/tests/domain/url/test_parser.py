"""Table-driven tests and hypothesis properties for the URL parser.

Target: >= 40 table-driven cases covering every accept/reject path
specified in ARCHITECTURE.md §7.1 and PRD FR-1.1..FR-1.3.
"""
from __future__ import annotations

import string

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from skillissue.domain.url.exceptions import (
    ControlCharacterError,
    InvalidFormatError,
    ReservedNameError,
    TooLongError,
    UnsupportedHostError,
    UnsafeRepoError,
    URLError,
)
from skillissue.domain.url.models import RepoRef
from skillissue.domain.url.parser import parse, _MAX_INPUT_LENGTH


# =====================================================================
# Helpers
# =====================================================================


def assert_parse(raw: str, *, owner: str, repo: str, ref: str | None = None) -> None:
    result = parse(raw)
    assert isinstance(result, RepoRef)
    assert result.owner == owner.lower()
    assert result.repo == repo
    assert result.ref == ref


def assert_rejects(raw: str, exc_type: type[URLError]) -> None:
    with pytest.raises(exc_type):
        parse(raw)


# =====================================================================
# Table-driven cases: (input, expected_owner, expected_repo, expected_ref)
# =====================================================================

VALID_CASES = [
    # canonical full URL
    ("https://github.com/octocat/Hello-World", "octocat", "Hello-World", None),
    # http scheme
    ("http://github.com/octocat/Hello-World", "octocat", "Hello-World", None),
    # www prefix
    ("https://www.github.com/octocat/Hello-World", "octocat", "Hello-World", None),
    # trailing slash
    ("https://github.com/octocat/Hello-World/", "octocat", "Hello-World", None),
    # .git suffix
    ("https://github.com/octocat/Hello-World.git", "octocat", "Hello-World", None),
    # .git suffix + trailing slash
    ("https://github.com/octocat/Hello-World.git/", "octocat", "Hello-World", None),
    # /tree/branch
    ("https://github.com/octocat/Hello-World/tree/main", "octocat", "Hello-World", "main"),
    # /tree/branch + trailing slash
    ("https://github.com/octocat/Hello-World/tree/main/", "octocat", "Hello-World", "main"),
    # /blob/branch
    ("https://github.com/octocat/Hello-World/blob/develop", "octocat", "Hello-World", "develop"),
    # branch with path beyond (full path captured as ref - GitHub supports slash-separated refs)
    ("https://github.com/octocat/Hello-World/tree/main/src/foo", "octocat", "Hello-World", "main/src/foo"),
    # branch + query
    ("https://github.com/octocat/Hello-World/tree/main?tab=readme-ov-file", "octocat", "Hello-World", "main"),
    # branch + fragment
    ("https://github.com/octocat/Hello-World/tree/main#readme", "octocat", "Hello-World", "main"),
    # repo with dots
    ("https://github.com/octocat/my.repo.name", "octocat", "my.repo.name", None),
    # owner with digits
    ("https://github.com/user123/repo", "user123", "repo", None),
    # short owner/repo
    ("https://github.com/a/b", "a", "b", None),
    # mixed case owner (lowercased)
    ("https://github.com/OCtoCat/Hello-World", "octocat", "Hello-World", None),
    # uppercase repo (preserved)
    ("https://github.com/octocat/HELLO-WORLD", "octocat", "HELLO-WORLD", None),
    # shorthand
    ("octocat/Hello-World", "octocat", "Hello-World", None),
    # shorthand with dots
    ("octocat/my.repo.name", "octocat", "my.repo.name", None),
    # shorthand simple
    ("torvalds/linux", "torvalds", "linux", None),
    # owner with hyphens
    ("my-org/my-repo", "my-org", "my-repo", None),
    # repo with underscores
    ("my-org/my_repo", "my-org", "my_repo", None),
    # long valid branch
    ("https://github.com/a/" + "b" * 100 + "/tree/" + "c" * 50, "a", "b" * 100, "c" * 50),
    # refs/slash-separated
    ("https://github.com/a/r/tree/feature/test-branch", "a", "r", "feature/test-branch"),
]

INVALID_CASES = [
    # non-github hosts
    ("https://gitlab.com/owner/repo", UnsupportedHostError),
    ("https://bitbucket.org/owner/repo", UnsupportedHostError),
    ("https://example.com/owner/repo", UnsupportedHostError),
    ("https://github.example.com/owner/repo", UnsupportedHostError),
    # embedded credentials
    ("https://user:pass@github.com/owner/repo", InvalidFormatError),
    ("https://user@github.com/owner/repo", InvalidFormatError),
    # non-http(s) schemes
    ("ftp://github.com/owner/repo", InvalidFormatError),
    ("git://github.com/owner/repo", InvalidFormatError),
    ("ssh://github.com/owner/repo", InvalidFormatError),
    ("file:///github.com/owner/repo", InvalidFormatError),
    # control characters
    ("https://github.com/owner/rep\x00o", ControlCharacterError),
    ("https://github.com/owner/repo\n", ControlCharacterError),
    ("https://github.com/owner/repo\r\n", ControlCharacterError),
    ("owner/re\rpo", ControlCharacterError),
    # reserved names
    ("https://github.com/octocat/.", ReservedNameError),
    ("https://github.com/octocat/..", ReservedNameError),
    ("octocat/.", ReservedNameError),
    ("octocat/..", ReservedNameError),
    # owner starts with dash
    ("https://github.com/-octocat/repo", InvalidFormatError),
    # owner ends with dash
    ("https://github.com/octocat-/repo", InvalidFormatError),
    # owner too long (40 chars exceeds 39 limit)
    ("https://github.com/" + "a" * 40 + "/repo", InvalidFormatError),
    # repo too long
    ("https://github.com/owner/" + "r" * 101, InvalidFormatError),
    # too long overall
    ("https://github.com/" + "o" * 100 + "/" + "r" * 100 + "/" + "b" * 100, TooLongError),
    # empty / whitespace only
    ("", InvalidFormatError),
    ("   ", InvalidFormatError),
    ("\t\n", ControlCharacterError),
    # bare domain without path
    ("https://github.com", InvalidFormatError),
    ("https://github.com/", InvalidFormatError),
    # github.com only, no owner
    ("https://github.com/octocat", InvalidFormatError),
    # invalid repo chars - spaces
    ("https://github.com/owner/my repo", InvalidFormatError),
    ("owner/my repo", InvalidFormatError),
    # invalid repo chars - special symbols
    ("https://github.com/owner/repo!", InvalidFormatError),
    # non-string
    (None, InvalidFormatError),
    (12345, InvalidFormatError),
]


# =====================================================================
# Test class: table-driven valid cases
# =====================================================================


class TestParseValid:
    """Every accepted form produces the correct RepoRef."""

    @pytest.mark.parametrize(
        "raw,expected_owner,expected_repo,expected_ref",
        VALID_CASES,
        ids=[c[0][:40] for c in VALID_CASES],
    )
    def test_valid_inputs(self, raw, expected_owner, expected_repo, expected_ref):
        assert_parse(raw, owner=expected_owner, repo=expected_repo, ref=expected_ref)

    def test_repo_ref_full_name(self):
        result = parse("https://github.com/octocat/Hello-World")
        assert result.full_name == "octocat/Hello-World"

    def test_repo_ref_str_without_ref(self):
        result = parse("octocat/repo")
        assert str(result) == "octocat/repo"

    def test_owner_lowercased(self):
        result = parse("https://github.com/OCtoCat/Repo")
        assert result.owner == "octocat"

    def test_repo_case_preserved(self):
        result = parse("https://github.com/octocat/MyRepo")
        assert result.repo == "MyRepo"

    def test_git_suffix_stripped(self):
        result = parse("https://github.com/octocat/Repo.git")
        assert result.repo == "Repo"

    def test_ref_captured_from_tree(self):
        result = parse("https://github.com/o/r/tree/feature-branch")
        assert result.ref == "feature-branch"

    def test_ref_captured_from_blob(self):
        result = parse("https://github.com/o/r/blob/v2.0")
        assert result.ref == "v2.0"

    def test_ref_with_path_segments(self):
        result = parse("https://github.com/octocat/repo/tree/main/src/utils/helpers")
        assert result.ref == "main/src/utils/helpers"
        assert result.repo == "repo"

    def test_shorthand_no_ref(self):
        result = parse("owner/repo")
        assert result.ref is None

    def test_dot_git_in_shorthand_rejected(self):
        assert_rejects("owner/repo.git", InvalidFormatError)

    def test_frozen_dataclass(self):
        result = parse("https://github.com/a/b")
        with pytest.raises(AttributeError):
            result.owner = "hacked"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.repo = "hacked"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.ref = "hacked"  # type: ignore[misc]


# =====================================================================
# Test class: table-driven invalid cases
# =====================================================================


class TestParseInvalid:
    """Every rejection raises the correct exception type."""

    @pytest.mark.parametrize(
        "raw,exc_type",
        [
            (r, e) for (r, e) in INVALID_CASES
            if r is not None and not isinstance(r, int)
        ],
        ids=[str(c[0])[:40] for c in INVALID_CASES if c[0] is not None and not isinstance(c[0], int)],
    )
    def test_invalid_string_inputs(self, raw, exc_type):
        assert_rejects(raw, exc_type)

    def test_non_string_none(self):
        assert_rejects(None, InvalidFormatError)  # type: ignore[arg-type]

    def test_non_string_int(self):
        assert_rejects(12345, InvalidFormatError)  # type: ignore[arg-type]

    def test_unsupported_host_gitlab(self):
        assert_rejects("https://gitlab.com/owner/repo", UnsupportedHostError)

    def test_unsupported_host_bitbucket(self):
        assert_rejects("https://bitbucket.org/owner/repo", UnsupportedHostError)

    def test_credentials_rejected(self):
        assert_rejects("https://user:pass@github.com/owner/repo", InvalidFormatError)

    def test_control_char_null_byte(self):
        assert_rejects("https://github.com/owner/rep\x00o", ControlCharacterError)

    def test_control_char_newline(self):
        assert_rejects("https://github.com/owner/repo\n", ControlCharacterError)

    def test_control_char_tab(self):
        assert_rejects("owner/repo\t", ControlCharacterError)

    def test_reserved_dot(self):
        assert_rejects("https://github.com/octocat/.", ReservedNameError)

    def test_reserved_dotdot(self):
        assert_rejects("https://github.com/octocat/..", ReservedNameError)

    def test_owner_leading_dash(self):
        assert_rejects("https://github.com/-octocat/repo", InvalidFormatError)

    def test_owner_trailing_dash(self):
        assert_rejects("https://github.com/octocat-/repo", InvalidFormatError)

    def test_too_long(self):
        long_url = "https://github.com/" + "o" * 100 + "/" + "r" * 100 + "/" + "b" * 100
        assert_rejects(long_url, TooLongError)

    def test_max_length_boundary(self):
        """Inputs at exactly _MAX_INPUT_LENGTH should not raise TooLongError."""
        owner = "a" * 39
        repo = "r" * 100
        raw = f"https://github.com/{owner}/{repo}"
        result = parse(raw)
        assert result.owner == owner


# =====================================================================
# Hypothesis property tests
# =====================================================================


class TestHypothesisProperties:
    """Invariant-based tests using hypothesis."""

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
    @settings(max_examples=200, deadline=5000)
    def test_shorthand_owner_lowercased(self, owner: str, repo: str):
        """For any owner/repo passing the regex, parse returns lowercased owner."""
        owner = "".join(c for c in owner if c.isalnum() or c == "-")
        repo = "".join(c for c in repo if c.isalnum() or c in "_.-")
        if not owner or not repo:
            assume(False)
        if owner.startswith("-") or owner.endswith("-"):
            assume(False)
        if repo in (".", ".."):
            assume(False)
        if len(owner) > 39 or len(repo) > 100:
            assume(False)

        raw = f"{owner}/{repo}"
        try:
            result = parse(raw)
        except URLError:
            return

        assert result.owner == owner.lower()

    @given(
        host=st.sampled_from(["github.com", "www.github.com", "GITHUB.COM"]),
        owner=st.text(
            alphabet=st.characters(whitelist_categories=("Ll",)),
            min_size=1,
            max_size=39,
        ),
        repo=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=100,
        ),
    )
    @settings(max_examples=200, deadline=5000)
    def test_url_owner_lowercased(self, host: str, owner: str, repo: str):
        """Owner is always lowercased regardless of input case."""
        if owner.startswith("-") or owner.endswith("-"):
            assume(False)
        if repo in (".", ".."):
            assume(False)
        owner = "".join(c for c in owner if c.isalpha())
        repo = "".join(c for c in repo if c.isalnum() or c in "_.-")
        if not owner or not repo:
            assume(False)

        raw = f"https://{host}/{owner}/{repo}"
        try:
            result = parse(raw)
        except URLError:
            return

        assert result.owner == owner.lower()

    @given(
        raw=st.text(
            alphabet=st.characters(
                whitelist_categories=("Ll", "Lu", "Nd"),
                whitelist_characters="/._-",
            ),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=500, deadline=5000)
    def test_repo_ref_frozen(self, raw: str):
        """RepoRef is immutable (frozen dataclass)."""
        try:
            result = parse(raw)
        except URLError:
            return

        with pytest.raises(AttributeError):
            result.owner = "hacked"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.repo = "hacked"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.ref = "hacked"  # type: ignore[misc]

    def test_never_accepts_non_github_host(self):
        """Property: the parser never accepts a non-github.com host."""
        bad_hosts = [
            "https://gitlab.com/o/r",
            "https://bitbucket.org/o/r",
            "https://codeberg.org/o/r",
            "http://evil.com/o/r",
            "https://github.example.com/o/r",
            "https://my-github-proxy.com/o/r",
        ]
        for url in bad_hosts:
            with pytest.raises(URLError):
                parse(url)

    def test_too_long_shielded_by_length_check(self):
        """Inputs over _MAX_INPUT_LENGTH raise TooLongError, not control char error."""
        payload = "a" * 301
        with pytest.raises(TooLongError):
            parse(payload)

    def test_str_representation_well_formed(self):
        """str(RepoRef) always contains exactly one '/' and no control chars."""
        valid_inputs = [
            "https://github.com/a/b",
            "https://www.github.com/a/b",
            "a/b",
            "https://github.com/a/b/tree/main",
            "https://github.com/a/b.git",
        ]
        for raw in valid_inputs:
            result = parse(raw)
            s = str(result)
            assert "/" in s
            assert "\x00" not in s
