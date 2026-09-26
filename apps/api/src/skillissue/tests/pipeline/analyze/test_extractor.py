"""Tests for tree-sitter symbol extraction (T-3.1)."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from skillissue.pipeline.analyze.extractor import (
    ChunkBoundary,
    ExtractionResult,
    Symbol,
    extract_symbols,
    get_symbol_boundaries,
    is_treesitter_available,
)


PY_SOURCE = textwrap.dedent("""\
    from typing import Optional

    class UserService:
        def __init__(self, db):
            self.db = db

        def find(self, user_id: int) -> Optional[dict]:
            return self.db.query(User).get(user_id)

    def create_user(name: str, email: str) -> UserService:
        return UserService()
""")


JS_SOURCE = textwrap.dedent("""\
    import { Router } from 'express';

    class AuthController {
        login(req, res) {
            const token = this.generateToken(req.body);
            return res.json({ token });
        }

        generateToken(payload) {
            return jwt.sign(payload, process.env.SECRET);
        }
    }

    const router = new Router();
    export default router;
""")


class TestIsTreesitterAvailable:
    def test_returns_bool(self):
        result = is_treesitter_available()
        assert isinstance(result, bool)

    def test_returns_true_when_installed(self):
        # tree-sitter + grammars should be installed in dev deps
        assert is_treesitter_available() is True


class TestExtractSymbolsPython:
    def test_extracts_functions(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        assert isinstance(result, ExtractionResult)

    def test_extracts_class(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        names = {s.name for s in result.symbols}
        assert "UserService" in names

    def test_extracts_methods(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        names = {s.name for s in result.symbols}
        assert "__init__" in names
        assert "find" in names

    def test_extracts_top_level_function(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        names = {s.name for s in result.symbols}
        assert "create_user" in names

    def test_symbol_kinds(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        kinds = {s.kind for s in result.symbols}
        assert "class" in kinds
        assert "function" in kinds

    def test_symbol_line_numbers(self):
        result = extract_symbols("user_service.py", PY_SOURCE)
        for sym in result.symbols:
            assert sym.line_start >= 1
            assert sym.line_end >= sym.line_start

    def test_empty_source(self):
        result = extract_symbols("empty.py", "")
        assert isinstance(result, ExtractionResult)
        assert len(result.symbols) == 0

    def test_no_symbols_source(self):
        source = "x = 1\ny = 2\n"
        result = extract_symbols("plain.py", source)
        assert len(result.symbols) == 0

    def test_extraction_result_has_file(self):
        result = ExtractionResult(file="x.py", symbols=[])
        assert result.file == "x.py"
        assert result.symbols == []
        assert result.parse_error is False

    def test_symbol_dataclass(self):
        sym = Symbol(
            kind="function",
            name="test_fn",
            file="x.py",
            line_start=1,
            line_end=3,
        )
        assert sym.name == "test_fn"
        assert sym.kind == "function"
        assert sym.line_start == 1


class TestExtractSymbolsJavaScript:
    @pytest.mark.skipif(
        not is_treesitter_available(), reason="tree-sitter not installed"
    )
    def test_extracts_js_class(self):
        result = extract_symbols("auth.js", JS_SOURCE)
        names = {s.name for s in result.symbols}
        assert "AuthController" in names

    @pytest.mark.skipif(
        not is_treesitter_available(), reason="tree-sitter not installed"
    )
    def test_extracts_js_methods(self):
        result = extract_symbols("auth.js", JS_SOURCE)
        names = {s.name for s in result.symbols}
        assert "login" in names
        assert "generateToken" in names


class TestGetSymbolBoundaries:
    def test_returns_sorted_list(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            f = os.path.join(tmpdir, "test.py")
            with open(f, "w") as fp:
                fp.write(PY_SOURCE)
            boundaries = get_symbol_boundaries(Path(tmpdir), "test.py")
            assert isinstance(boundaries, list)
            for i in range(len(boundaries) - 1):
                assert boundaries[i].line_start <= boundaries[i + 1].line_start

    def test_non_empty_when_symbols_exist(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            f = os.path.join(tmpdir, "test.py")
            with open(f, "w") as fp:
                fp.write(PY_SOURCE)
            boundaries = get_symbol_boundaries(Path(tmpdir), "test.py")
            assert len(boundaries) > 0

    def test_chunk_boundary_fields(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            f = os.path.join(tmpdir, "test.py")
            with open(f, "w") as fp:
                fp.write(PY_SOURCE)
            boundaries = get_symbol_boundaries(Path(tmpdir), "test.py")
            if boundaries:
                b = boundaries[0]
                assert isinstance(b, ChunkBoundary)
                assert isinstance(b.line_start, int)
                assert b.line_start >= 1

    def test_empty_source_empty_boundaries(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            f = os.path.join(tmpdir, "test.py")
            with open(f, "w") as fp:
                fp.write("")
            boundaries = get_symbol_boundaries(Path(tmpdir), "test.py")
            assert boundaries == []


class TestExtractSymbolsRobustness:
    def test_binary_like_source(self):
        result = extract_symbols("weird.bin", "\x00\x01\x02\x03")
        assert isinstance(result, ExtractionResult)

    def test_very_long_lines(self):
        long_line = "x = " + "a" * 10000 + "\n"
        result = extract_symbols("long.py", long_line)
        assert isinstance(result, ExtractionResult)

    def test_unicode_source(self):
        source = "# 日本語のコメント\nclass ユーザー:\n    pass\n"
        result = extract_symbols("unicode.py", source)
        assert isinstance(result, ExtractionResult)
