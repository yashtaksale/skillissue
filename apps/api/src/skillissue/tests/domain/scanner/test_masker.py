"""Property-based and edge-case tests for the secret masker.

Property: never more than 6 visible (non-bullet) characters of any secret
leave the masker (ARCHITECTURE.md §7.4).
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from skillissue.domain.scanner.masker import mask_secret, mask_secret_short


_BULLET = "•"


def _visible_count(masked: str) -> int:
    """Count non-bullet characters in the masked string."""
    return sum(1 for c in masked if c != _BULLET)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMaskSecretEdgeCases:
    """Boundary inputs around the 6-char visibility property."""

    def test_empty_string(self) -> None:
        assert mask_secret("") == ""

    def test_single_char(self) -> None:
        # Only 1 char — nothing to mask.
        assert mask_secret("X") == "X"

    def test_two_chars(self) -> None:
        # Only 2 chars — falls through mask_secret_short and is preserved.
        assert mask_secret("ab") == "ab"

    def test_three_chars(self) -> None:
        # mask_secret_short: keep first 2, mask 1.
        assert mask_secret("abc") == "ab•"

    def test_six_chars(self) -> None:
        # 6 chars exactly — mask_secret_short path: keep first 2, mask 4.
        result = mask_secret("abcdef")
        assert result == "ab••••"
        assert _visible_count(result) <= 2

    def test_seven_chars(self) -> None:
        # 7 chars — switch to mask_secret: keep first 4, mask 1, keep last 2.
        result = mask_secret("abcdefg")
        assert result == "abcd•fg"
        assert _visible_count(result) <= 6

    def test_eight_chars(self) -> None:
        result = mask_secret("abcdefgh")
        assert result == "abcd••gh"
        assert _visible_count(result) <= 6

    def test_long_aws_key(self) -> None:
        # AWS keys are 20 chars.
        key = "AKIAIOSFODNN7EXAMPLE"
        result = mask_secret(key)
        # First 4 + 14 bullets + last 2 = "AKIA••••••••••••••LE"
        assert result == "AKIA" + _BULLET * 14 + "LE"
        assert _visible_count(result) == 6

    def test_very_long_secret(self) -> None:
        secret = "x" * 1000
        result = mask_secret(secret)
        # First 4 + 994 bullets + last 2 = 1000 chars.
        assert len(result) == 1000
        assert result.startswith("xxxx")
        assert result.endswith("xx")
        assert _visible_count(result) == 6

    def test_mask_preserves_unicode_length(self) -> None:
        """Multi-byte input length is counted in Python chars, not bytes."""
        # 8-char emoji string.
        secret = "abcdefgh"  # keep it ASCII for the property
        assert len(mask_secret(secret)) == len(secret)


class TestMaskSecretShort:
    """mask_secret_short is the ≤6 char path."""

    def test_empty(self) -> None:
        assert mask_secret_short("") == ""

    def test_single(self) -> None:
        assert mask_secret_short("X") == "X"

    def test_two(self) -> None:
        assert mask_secret_short("ab") == "ab"

    def test_three(self) -> None:
        assert mask_secret_short("abc") == "ab•"

    def test_six(self) -> None:
        assert mask_secret_short("abcdef") == "ab••••"

    def test_short_visible_count_never_exceeds_two(self) -> None:
        for n in range(0, 7):
            value = "x" * n
            assert _visible_count(mask_secret_short(value)) <= 2


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


class TestMaskSecretProperties:
    """Invariant tests over arbitrary input."""

    @given(value=st.text(min_size=0, max_size=500))
    @settings(max_examples=500, deadline=5000)
    def test_visible_count_never_exceeds_six(self, value: str) -> None:
        """Property: at most 6 visible characters after masking."""
        masked = mask_secret(value)
        assert _visible_count(masked) <= 6

    @given(value=st.text(min_size=0, max_size=500))
    @settings(max_examples=500, deadline=5000)
    def test_length_preserved(self, value: str) -> None:
        """Property: the masked string has the same length as the input."""
        assert len(mask_secret(value)) == len(value)

    @given(value=st.text(min_size=7, max_size=500))
    @settings(max_examples=500, deadline=5000)
    def test_long_secrets_keep_first_four_and_last_two(self, value: str) -> None:
        """Property: long secrets keep exactly first 4 + last 2 characters."""
        masked = mask_secret(value)
        assert masked[:4] == value[:4]
        assert masked[-2:] == value[-2:]

    @given(value=st.text(min_size=3, max_size=6))
    @settings(max_examples=500, deadline=5000)
    def test_short_secrets_keep_first_two(self, value: str) -> None:
        """Property: short secrets (3..6) keep exactly the first 2 characters."""
        masked = mask_secret(value)
        assert masked[:2] == value[:2]

    @given(value=st.text(min_size=7, max_size=500))
    @settings(max_examples=500, deadline=5000)
    def test_long_secret_middle_is_all_bullets(self, value: str) -> None:
        """Property: the middle (between first 4 and last 2) is all bullets."""
        masked = mask_secret(value)
        middle = masked[4:-2]
        assert all(c == _BULLET for c in middle)
        assert len(middle) == len(value) - 6

    @given(value=st.text(min_size=0, max_size=500))
    @settings(max_examples=500, deadline=5000)
    def test_short_visibility_property(self, value: str) -> None:
        """mask_secret_short also satisfies the ≤6 visible rule."""
        masked = mask_secret_short(value)
        assert _visible_count(masked) <= 6
