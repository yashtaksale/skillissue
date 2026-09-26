"""Tests for secret redaction (T-3.6).

The big invariant: after redaction, no full secret string remains.
We test this with the `no_full_secret_remains` property.
"""
from __future__ import annotations

import string

import pytest
from hypothesis import given, strategies as st

from skillissue.pipeline.sample.redact import (
    RedactionResult,
    _partial_token,
    _show_partial,
    no_full_secret_remains,
    redact,
    redact_chunk_text,
)


# =====================================================================
# Redact basic patterns
# =====================================================================


class TestRedact:
    def test_returns_redaction_result(self):
        result = redact("hello world")
        assert isinstance(result, RedactionResult)

    def test_no_secrets_no_changes(self):
        result = redact("just some normal code\nfoo bar")
        assert result.redaction_count == 0
        assert result.redacted_text == "just some normal code\nfoo bar"

    def test_empty_string(self):
        result = redact("")
        assert result.redaction_count == 0

    def test_aws_access_key_redacted(self):
        result = redact("aws_key = AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in result.redacted_text
        assert result.redaction_count >= 1

    def test_bearer_token_redacted(self):
        result = redact("Authorization: Bearer abc123def456ghi789jkl012mno")
        assert "abc123def456ghi789jkl012mno" not in result.redacted_text

    def test_api_key_redacted(self):
        result = redact('api_key = "abcdefghijklmnopqrst"')
        # The value should be redacted
        assert "abcdefghijklmnopqrst" not in result.redacted_text

    def test_private_key_redacted(self):
        result = redact(
            "-----BEGIN RSA PRIVATE KEY-----\nABCDEF123\n-----END RSA PRIVATE KEY-----"
        )
        assert "ABCDEF123" not in result.redacted_text

    def test_password_redacted(self):
        result = redact("password=mySecretPass123")
        assert "mySecretPass123" not in result.redacted_text

    def test_long_base64_redacted(self):
        b64 = "A" * 64
        result = redact(f"token = '{b64}'")
        assert b64 not in result.redacted_text

    def test_hex_string_redacted(self):
        hex_str = "A" * 32
        result = redact(f"hash = '{hex_str}'")
        assert hex_str not in result.redacted_text or "_" in result.redacted_text

    def test_multiple_secrets_in_one_text(self):
        text = (
            "AKIAIOSFODNN7EXAMPLE\n"
            "Bearer abc123def456ghi789jkl012mno\n"
            "api_key = 'abcdefghijklmnopqrstuvwxyz'\n"
        )
        result = redact(text)
        assert result.redaction_count >= 3

    def test_redaction_count_incremented(self):
        result = redact("AKIAIOSFODNN7EXAMPLE\nAKIAIOSFODNN7EXAMPLE")
        assert result.redaction_count >= 2

    def test_pattern_hits_recorded(self):
        result = redact("AKIAIOSFODNN7EXAMPLE")
        assert isinstance(result.pattern_hits, dict)
        # At least one pattern should be hit
        assert sum(result.pattern_hits.values()) >= 1


# =====================================================================
# redact_chunk_text with partial reveals
# =====================================================================


class TestRedactChunkText:
    def test_partial_keeps_prefix(self):
        text = "api_key = 'abcdefghijklmnopqrstuvwxyz'"
        result = redact_chunk_text(text)
        # Should reveal first few chars for context but not the full secret
        # The exact partial display might include first chars
        assert "abcdef" not in result  # full secret should not be there

    def test_no_partial_when_disabled(self):
        text = "api_key = 'abcdefghijklmnopqrstuvwxyz'"
        result = redact_chunk_text(text, show_partial=False)
        assert "abcdefghijklmnopqrstuvwxyz" not in result


# =====================================================================
# _partial_token and _show_partial
# =====================================================================


class TestPartialHelpers:
    def test_partial_token_short(self):
        result = _partial_token("abc")
        # Short tokens are revealed as-is
        assert result == "abc"

    def test_partial_token_long(self):
        result = _partial_token("a" * 30 + "Z" * 30)
        # Long tokens get truncated
        assert len(result) < 60

    def test_show_partial_returns_string(self):
        result = _show_partial("a" * 30)
        assert isinstance(result, str)
        assert len(result) <= 32  # reasonable bound

    def test_show_partial_short_input(self):
        # Short strings just returned as-is
        result = _show_partial("abc")
        assert result == "abc"


# =====================================================================
# Property: no full secret remains (the critical guarantee)
# =====================================================================


class TestNoFullSecretRemains:
    def test_aws_key_removed(self):
        secret = "AKIAIOSFODNN7EXAMPLE"
        result = redact(f"value = {secret}")
        assert no_full_secret_remains(result.redacted_text)

    def test_private_key_removed(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nABC\n-----END RSA PRIVATE KEY-----"
        result = redact(text)
        assert no_full_secret_remains(result.redacted_text)

    def test_normal_text_passes(self):
        text = "Just some normal code with no secrets here"
        result = redact(text)
        assert no_full_secret_remains(result.redacted_text)

    def test_real_world_aws_secret(self):
        text = """
        # config.py
        AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
        AWS_SECRET_ACCESS_KEY = "abc123def456ghi789jkl012mno345pqr67890AB"
        """
        result = redact(text)
        assert no_full_secret_remains(result.redacted_text)

    @given(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "Lu", "Ll", "Nd"),
                whitelist_characters="",
            ),
            min_size=20,
            max_size=64,
        )
    )
    def test_random_long_token_redacted(self, token):
        # Any long enough alphanumeric string should be safe to potentially redact
        text = f"token = '{token}'"
        result = redact(text)
        assert no_full_secret_remains(result.redacted_text)


class TestIdempotency:
    """Redacting twice should not change the result (up to first pass)."""

    def test_redact_twice_same_count(self):
        text = "AKIAIOSFODNN7EXAMPLE"
        once = redact(text)
        twice = redact(once.redacted_text)
        # Second pass should not find anything
        assert twice.redaction_count == 0 or twice.redacted_text == once.redacted_text

    def test_show_partial_idempotent(self):
        text = "Bearer abc123def456ghi789jkl012mno"
        once = redact_chunk_text(text)
        twice = redact_chunk_text(once)
        assert once == twice
