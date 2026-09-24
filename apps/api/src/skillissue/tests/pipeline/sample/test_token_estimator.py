"""Tests for the token estimator."""
from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from skillissue.pipeline.sample.token_estimator import (
    TokenBudget,
    estimate_tokens,
    estimate_tokens_batch,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_char(self):
        assert estimate_tokens("a") == 1

    def test_exact_three_chars(self):
        tokens = estimate_tokens("abc")
        assert tokens >= 1

    def test_roughly_chars_divided_by_3_2(self):
        # 320 chars ≈ 100 tokens
        assert estimate_tokens("x" * 320) >= 95
        assert estimate_tokens("x" * 320) <= 110

    def test_batch_empty(self):
        assert estimate_tokens_batch([]) == 0

    def test_batch_multiple(self):
        assert estimate_tokens_batch(["hello", "world"]) == estimate_tokens("hello") + estimate_tokens("world")


class TestTokenBudget:
    def test_within_budget(self):
        b = TokenBudget(100)
        assert b.add("hello") is True
        assert b.remaining() < 100

    def test_exceeds_budget(self):
        b = TokenBudget(10)
        assert b.add("x" * 100_000) is False
        assert b.used == 0  # not consumed when rejected

    def test_remaining(self):
        b = TokenBudget(200)
        b.add("test")
        assert b.remaining() == 199

    def test_repr(self):
        b = TokenBudget(100)
        r = repr(b)
        assert "used=" in r
        assert "max=100" in r


class TestEstimateTokensProperties:
    @given(st.text())
    def test_never_negative(self, text):
        assert estimate_tokens(text) >= 0

    @given(st.integers(min_value=1, max_value=10000))
    def test_proportional_to_length(self, length):
        assert estimate_tokens("x" * length) >= 1
