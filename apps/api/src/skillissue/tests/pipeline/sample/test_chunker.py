"""Tests for the overlap-aware chunker (T-3.2)."""
from __future__ import annotations

import os
import textwrap

from pathlib import Path

import pytest

from skillissue.pipeline.sample.chunker import (
    Chunk,
    ChunkBudget,
    _build_context_header,
    chunk_files,
    chunk_repo,
    render_chunk,
    render_chunk_source,
)


# === Helpers ===


def _write(tmp_path, name: str, lines: int = 30) -> str:
    """Write a file and return a relative path from tmp_path.

    `lines` iterations of ~12 lines of Python code → ~360 lines, ~700 tokens.
    """
    p = tmp_path / name
    content = "\n".join(
        f"# line {i} with some longer comment text\n"
        f"# second line of comment for line {i} explaining the meaning\n"
        f"def function_{i}(x, y=None, z=None):\n"
        f"    \"\"\"Process value {i} with full docstring.\"\"\"\n"
        f"    result = x * {i} + y if y else 0\n"
        f"    if result > 100:\n"
        f"        z = z or 'default'\n"
        f"        return str(result) + z\n"
        f"    return result\n"
        f"\n"
        f"# separator comment for next block\n"
        f"\n"
        for i in range(lines)
    ) + "\n"
    p.write_text(content)
    return name  # relative path (file is in source_dir root)


def _write_complex(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content)
    return str(p)


# === Chunk dataclass tests ===


class TestChunk:
    def test_defaults(self):
        c = Chunk(
            chunk_id=0,
            files=[],
            total_lines=0,
            total_bytes=0,
            estimated_tokens=0,
        )
        assert c.content == ""
        assert c.selection_reason == ""
        assert c.overlap_with == -1

    def test_basic_construction(self):
        c = Chunk(
            chunk_id=1,
            files=["a.py"],
            total_lines=100,
            total_bytes=500,
            estimated_tokens=100,
        )
        assert c.chunk_id == 1
        assert c.files == ["a.py"]
        assert c.estimated_tokens == 100


# === ChunkBudget tests ===


class TestChunkBudget:
    def test_defaults(self):
        b = ChunkBudget()
        assert b.max_tokens == 6_000
        assert b.min_tokens == 200
        assert b.overlap_lines == 20


# === Context header tests ===


class TestBuildContextHeader:
    def test_header_contains_filename(self):
        h = _build_context_header("src/auth.py", 200, 1500)
        assert "src/auth.py" in h

    def test_header_contains_line_count(self):
        h = _build_context_header("a.py", 200, 1500)
        assert "200" in h

    def test_header_contains_token_count(self):
        h = _build_context_header("a.py", 200, 1500)
        assert "1500" in h

    def test_header_uses_border(self):
        h = _build_context_header("a.py", 1, 1)
        assert "=" in h


# === chunk_files tests ===


class TestChunkFiles:
    def _chunk(self, tmp_path, file_paths, budget=None):
        return chunk_files(Path(tmp_path), file_paths, budget=budget)

    def test_empty_file_list(self, tmp_path):
        chunks = self._chunk(tmp_path, [])
        assert chunks == []

    def test_single_file(self, tmp_path):
        path = _write(tmp_path, "a.py", lines=20)
        chunks = self._chunk(tmp_path, [path])
        assert len(chunks) == 1
        assert chunks[0].files == [path]

    def test_chunk_ids_unique(self, tmp_path):
        paths = [_write(tmp_path, f"f{i}.py") for i in range(3)]
        chunks = self._chunk(tmp_path, paths)
        ids = [c.chunk_id for c in chunks]
        assert len(set(ids)) == len(ids)

    def test_files_appear_in_some_chunk(self, tmp_path):
        paths = [_write(tmp_path, f"f{i}.py") for i in range(5)]
        chunks = self._chunk(tmp_path, paths)
        all_files = [f for c in chunks for f in c.files]
        for p in paths:
            assert p in all_files

    def test_multiple_chunks_when_budget_exceeded(self, tmp_path):
        paths = [_write(tmp_path, f"f{i}.py", lines=200) for i in range(4)]
        budget = ChunkBudget(max_chunks=10, max_files_per_chunk=1)
        chunks = self._chunk(tmp_path, paths, budget=budget)
        assert len(chunks) >= 2

    def test_token_count_populated(self, tmp_path):
        path = _write(tmp_path, "a.py", lines=100)
        chunks = self._chunk(tmp_path, [path])
        assert chunks[0].estimated_tokens > 0

    def test_overlap_marked_on_second_chunk(self, tmp_path):
        f1 = _write(tmp_path, "a.py", lines=200)
        f2 = _write(tmp_path, "b.py", lines=200)
        budget = ChunkBudget(max_chunks=10, max_files_per_chunk=1, overlap_lines=5)
        chunks = self._chunk(tmp_path, [f1, f2], budget=budget)
        if len(chunks) > 1:
            # second chunk should reference the first (overlap)
            assert chunks[1].overlap_with >= 0

    def test_chunk_within_max_files(self, tmp_path):
        paths = [_write(tmp_path, f"f{i}.py", lines=10) for i in range(5)]
        budget = ChunkBudget(max_files_per_chunk=2)
        chunks = self._chunk(tmp_path, paths, budget=budget)
        for c in chunks:
            assert len(c.files) <= 2

    def test_selection_reason_field_exists(self, tmp_path):
        path = _write(tmp_path, "a.py", lines=20)
        chunks = self._chunk(tmp_path, [path])
        # selection_reason exists on Chunk (set by selector, not chunker)
        assert hasattr(chunks[0], "selection_reason")


# === chunk_repo backward compat ===


class TestChunkRepo:
    def test_backward_compat_wrapper(self, tmp_path):
        f1 = _write(tmp_path, "a.py", lines=50)
        f2 = _write(tmp_path, "b.py", lines=50)
        chunks = chunk_repo(tmp_path, [f1, f2])
        assert len(chunks) >= 1


# === Render functions ===


class TestRenderChunk:
    def test_returns_string(self, tmp_path):
        path = _write(tmp_path, "a.py", lines=10)
        chunks = chunk_files(Path(tmp_path), [path])
        rendered = render_chunk(chunks[0], Path(tmp_path))
        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_renders_chunk_id(self, tmp_path):
        path = _write(tmp_path, "a.py", lines=10)
        chunks = chunk_files(Path(tmp_path), [path])
        rendered = render_chunk(chunks[0], Path(tmp_path))
        assert str(chunks[0].chunk_id) in rendered

    def test_renders_source(self, tmp_path):
        path = _write(tmp_path, "unique_marker.py", lines=10)
        chunks = chunk_files(Path(tmp_path), [path])
        rendered = render_chunk_source(chunks[0], Path(tmp_path))
        assert isinstance(rendered, str)
