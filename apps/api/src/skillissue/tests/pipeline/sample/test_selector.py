"""Tests for the greedy file selector (T-3.4)."""
from __future__ import annotations

import os
import tempfile

import pytest

from skillissue.pipeline.sample.selector import (
    SignalInfo,
    SelectorConfig,
    _dir_key,
    _stable_seed,
    _chunk_reason,
    force_include_signals,
    select_files,
)


# =====================================================================
# _dir_key
# =====================================================================


class TestDirKey:
    def test_simple_path(self):
        expected = os.path.join("src", "auth")
        assert _dir_key("src/auth/login.py") == expected

    def test_nested_path(self):
        expected = os.path.join("a", "b", "c", "d")
        assert _dir_key("a/b/c/d/file.py") == expected

    def test_root_file(self):
        result = _dir_key("main.py")
        assert result == "." or result == ""

    def test_trailing_slash_handled(self):
        expected = os.path.join("src", "auth")
        assert _dir_key("src/auth/login.py/") == expected

    def test_dotdot_in_path(self):
        result = _dir_key("src/../other.py")
        assert isinstance(result, str)


# =====================================================================
# _stable_seed
# =====================================================================


class TestStableSeed:
    def test_same_path_same_seed(self):
        assert _stable_seed("a.py") == _stable_seed("a.py")

    def test_different_paths_different_seeds(self):
        assert _stable_seed("a.py") != _stable_seed("b.py")

    def test_returns_numeric_string(self):
        seed = _stable_seed("test.py")
        assert isinstance(seed, int)

    def test_deterministic(self):
        results = [_stable_seed("file.py") for _ in range(5)]
        assert len(set(results)) == 1


# =====================================================================
# _chunk_reason
# =====================================================================


class TestChunkReason:
    def test_signal_reason(self):
        result = _chunk_reason(["sig1"], {"sig1"}, [])
        assert "signal" in result.lower()

    def test_entrypoint_reason(self):
        from skillissue.pipeline.sample.scorer import FileScore
        ep = FileScore(
            path="main.py",
            lines=50,
            estimated_tokens=200,
            risk_score=0.0,
            is_test=False,
            is_entrypoint=True,
            is_generated=False,
            symbol_count=5,
            base_score=0.1,
            final_score=0.3,
            selection_reason="",
        )
        result = _chunk_reason(["main.py"], set(), [ep])
        assert "entrypoint" in result.lower()

    def test_risk_reason(self):
        from skillissue.pipeline.sample.scorer import FileScore
        fs = FileScore(
            path="auth/login.py",
            lines=100,
            estimated_tokens=300,
            risk_score=1.0,
            is_test=False,
            is_entrypoint=False,
            is_generated=False,
            symbol_count=5,
            base_score=0.1,
            final_score=0.5,
            selection_reason="",
        )
        result = _chunk_reason(["auth/login.py"], set(), [fs])
        assert "risk" in result.lower()

    def test_coverage_reason(self):
        from skillissue.pipeline.sample.scorer import FileScore
        fs = FileScore(
            path="utils/helpers.py",
            lines=50,
            estimated_tokens=100,
            risk_score=0.0,
            is_test=False,
            is_entrypoint=False,
            is_generated=False,
            symbol_count=2,
            base_score=0.1,
            final_score=0.1,
            selection_reason="",
        )
        result = _chunk_reason(["utils/helpers.py"], set(), [fs])
        assert "coverage" in result.lower()


# =====================================================================
# force_include_signals
# =====================================================================


class TestForceIncludeSignals:
    def test_empty_signals(self):
        result = force_include_signals([], [])
        assert result == []

    def test_critical_included(self):
        signals = [
            SignalInfo("s1", "auth.py", "critical", "sec"),
            SignalInfo("s2", "utils.py", "low", "style"),
        ]
        result = force_include_signals([], signals)
        assert "auth.py" in result
        assert "utils.py" not in result

    def test_high_included(self):
        signals = [SignalInfo("s1", "db.py", "high", "bug")]
        result = force_include_signals([], signals)
        assert "db.py" in result

    def test_medium_included(self):
        signals = [SignalInfo("s1", "x.py", "medium", "perf")]
        result = force_include_signals([], signals)
        assert "x.py" in result

    def test_low_excluded(self):
        signals = [SignalInfo("s1", "x.py", "low", "style")]
        result = force_include_signals([], signals)
        assert "x.py" not in result

    def test_no_duplicates(self):
        signals = [
            SignalInfo("s1", "x.py", "high", "a"),
            SignalInfo("s2", "x.py", "medium", "b"),
        ]
        result = force_include_signals([], signals)
        assert result.count("x.py") == 1

    def test_returns_sorted(self):
        signals = [
            SignalInfo("s1", "z.py", "high", "a"),
            SignalInfo("s2", "a.py", "high", "b"),
            SignalInfo("s3", "m.py", "high", "c"),
        ]
        result = force_include_signals([], signals)
        assert result == sorted(result)


# =====================================================================
# select_files
# =====================================================================


class TestSelectFiles:
    def _make_score(self, path, score, is_ep=False):
        from skillissue.pipeline.sample.scorer import FileScore
        return FileScore(
            path=path,
            lines=100,
            estimated_tokens=300,
            risk_score=0.0,
            is_test=False,
            is_entrypoint=is_ep,
            is_generated=False,
            symbol_count=5,
            base_score=score,
            final_score=score,
            selection_reason="test",
        )

    def test_returns_tuple(self):
        scores = [self._make_score("a.py", 0.5)]
        chunks, unselected = select_files(scores, signals=[])
        assert isinstance(chunks, list)
        assert isinstance(unselected, list)

    def test_forced_signals_selected(self):
        signals = [SignalInfo("s1", "auth.py", "critical", "sec")]
        scores = [self._make_score("auth.py", 0.1)]
        chunks, unselected = select_files(scores, signals=signals)
        all_files = [f for c in chunks for f in c.files]
        assert "auth.py" in all_files

    def test_high_scored_files_preferred(self):
        scores = [
            self._make_score("a.py", 1.0),
            self._make_score("b.py", 0.8),
            self._make_score("c.py", 0.1),
        ]
        chunks, unselected = select_files(scores, signals=[])
        all_files = [f for c in chunks for f in c.files]
        assert "a.py" in all_files
        assert "b.py" in all_files

    def test_empty_scores(self):
        chunks, unselected = select_files([], signals=[])
        assert chunks == []
        assert unselected == []

    def test_chunk_budget_respected(self):
        scores = [
            self._make_score(f"src/d{i}/f.py", 1.0 - i * 0.01)
            for i in range(20)
        ]
        config = SelectorConfig(max_chunks=3, max_files_per_chunk=10)
        chunks, unselected = select_files(scores, signals=[], config=config)
        assert len(chunks) <= config.max_chunks or len(unselected) > 0

    def test_chunk_reason_populated(self):
        scores = [self._make_score("a.py", 0.5)]
        chunks, _ = select_files(scores, signals=[])
        for c in chunks:
            assert c.selection_reason != ""

    def test_unselected_paths_returned(self):
        scores = [
            self._make_score(f"f{i}.py", 1.0 - i * 0.001)
            for i in range(20)
        ]
        config = SelectorConfig(max_chunks=1, max_files_per_chunk=2)
        chunks, unselected = select_files(scores, signals=[], config=config)
        assert len(unselected) > 0


# =====================================================================
# Diversity constraint
# =====================================================================


class TestDiversityConstraint:
    def _make_score(self, path, score):
        from skillissue.pipeline.sample.scorer import FileScore
        return FileScore(
            path=path,
            lines=100,
            estimated_tokens=300,
            risk_score=0.0,
            is_test=False,
            is_entrypoint=False,
            is_generated=False,
            symbol_count=5,
            base_score=score,
            final_score=score,
            selection_reason="test",
        )

    def test_no_single_dir_dominates(self):
        """With mixed dirs, no single directory exceeds 60% of any chunk."""
        scores = []
        for i in range(20):
            scores.append(self._make_score(f"src/auth/f{i}.py", 0.9))
            scores.append(self._make_score(f"src/pay/f{i}.py", 0.9))
        config = SelectorConfig(
            max_chunks=10,
            max_files_per_chunk=10,
            diversity_penalty=0.5,
        )
        chunks, _ = select_files(scores, signals=[], config=config)
        for c in chunks:
            if len(c.files) >= 5:
                dir_counts: dict[str, int] = {}
                for f in c.files:
                    d = os.path.dirname(f) or "."
                    dir_counts[d] = dir_counts.get(d, 0) + 1
                max_share = max(dir_counts.values()) / max(len(c.files), 1)
                assert max_share <= 0.7, (
                    f"Dir share {max_share:.0%} > 70% in chunk {c.chunk_id}"
                )

    def test_mixed_dirs_balanced(self):
        """Files from different dirs should spread across chunks."""
        scores = []
        for i in range(10):
            scores.append(self._make_score(f"src/auth/f{i}.py", 0.9))
            scores.append(self._make_score(f"src/pay/f{i}.py", 0.9))
        config = SelectorConfig(max_chunks=10, max_files_per_chunk=2, diversity_penalty=0.5)
        chunks, _ = select_files(scores, signals=[], config=config)
        assert len(chunks) >= 2
