"""Tree-sitter based source code extraction (T-3.1).

Extracts functions, classes, and methods with line ranges from Python,
JavaScript, and TypeScript files. Handles syntax-error files without crashing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# =====================================================================
# Data model
# =====================================================================


@dataclass(frozen=True)
class Symbol:
    """A function, class, or method extracted from source code."""

    kind: str          # "function" | "class" | "method" | "interface" | "type_alias"
    name: str
    file: str          # relative path
    line_start: int    # 1-indexed inclusive
    line_end: int      # 1-indexed inclusive
    signature: str = ""

    @property
    def lines(self) -> int:
        return self.line_end - self.line_start + 1

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "name": self.name,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "lines": self.lines,
            "signature": self.signature,
        }


@dataclass
class ExtractionResult:
    """Result of extracting symbols from a file."""

    file: str
    symbols: list[Symbol]
    parse_error: bool = False
    language: str | None = None


# =====================================================================
# Lazy tree-sitter loading
# =====================================================================


def _load_languages() -> dict:
    """Load tree-sitter and the three grammars, returning a registry.

    Returns an empty dict if any of the dependencies are missing.
    """
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_javascript

    langs = {}
    for name, mod in [
        ("python", tree_sitter_python),
        ("javascript", tree_sitter_javascript),
    ]:
        langs[name] = tree_sitter.Language(mod.language())
    return langs


_LANGS: dict | None = None


def _get_languages() -> dict:
    global _LANGS
    if _LANGS is None:
        try:
            _LANGS = _load_languages()
        except Exception:
            _LANGS = {}
    return _LANGS


# =====================================================================
# Language mapping
# =====================================================================


_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",   # use JS grammar for TS (broad coverage)
    ".tsx": "javascript",
    ".mts": "javascript",
    ".cts": "javascript",
}


# S-expression queries for each language
_QUERIES: dict[str, str] = {
    "python": """
        (function_definition name: (identifier) @name) @function
        (class_definition name: (identifier) @name) @class
    """,
    "javascript": """
        (function_declaration name: (identifier) @name) @function
        (class_declaration name: (identifier) @name) @class
        (method_definition name: (property_identifier) @name) @method
    """,
}


_KIND_MAP = {
    "function": "function",
    "class": "class",
    "method": "method",
}


# =====================================================================
# Core extraction
# =====================================================================


def _read_file(path: Path) -> bytes:
    """Read file as bytes for tree-sitter."""
    try:
        return path.read_bytes()
    except (OSError, PermissionError):
        return b""


def _decode_node(node, source: bytes) -> str:
    """Decode source text for a node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _signature(source: bytes, node) -> str:
    """Extract a one-line signature for a node."""
    text = _decode_node(node, source).split("\n", 1)[0]
    return text[:120]


def extract_symbols(file: str, source: str | bytes) -> ExtractionResult:
    """Extract all symbols from a source file.

    Args:
        file: Relative path of the file (for language detection).
        source: Raw file bytes (or str, which will be encoded).

    Returns:
        ExtractionResult with symbols and any parse error flag.
    """
    ext = Path(file).suffix.lower()
    language_name = _EXT_TO_LANG.get(ext)
    if language_name is None:
        return ExtractionResult(file=file, symbols=[], language=None)

    if isinstance(source, str):
        source = source.encode("utf-8")

    if not source or not source.strip():
        return ExtractionResult(file=file, symbols=[], language=language_name, parse_error=False)

    langs = _get_languages()
    lang = langs.get(language_name)
    if lang is None:
        return ExtractionResult(
            file=file,
            symbols=[],
            language=language_name,
            parse_error=True,
        )

    try:
        import tree_sitter
        parser = tree_sitter.Parser()
        parser.language = lang
        tree = parser.parse(source)
    except Exception:
        return ExtractionResult(
            file=file,
            symbols=[],
            language=language_name,
            parse_error=True,
        )

    if tree is None or tree.root_node is None:
        return ExtractionResult(
            file=file,
            symbols=[],
            language=language_name,
            parse_error=True,
        )

    query_str = _QUERIES.get(language_name, "")
    symbols: list[Symbol] = []

    try:
        import tree_sitter
        query = tree_sitter.Query(lang, query_str)
        cursor = tree_sitter.QueryCursor(query)
        results = cursor.matches(tree.root_node)
    except Exception:
        # Bad query → fall back to linear walk (still gets functions)
        symbols = _linear_walk(tree.root_node, file, source, language_name)
        return ExtractionResult(
            file=file,
            symbols=symbols,
            language=language_name,
            parse_error=False,
        )

    for _pattern_idx, captures in results:
        kind_node = None
        name_node = None
        for cap_name, nodes in captures.items():
            for node in nodes:
                if cap_name in _KIND_MAP and kind_node is None:
                    kind_node = (cap_name, node)
                if cap_name == "name" and name_node is None:
                    name_node = node

        if kind_node is None or name_node is None:
            continue

        cap_kind, cap_node = kind_node
        kind = _KIND_MAP[cap_kind]
        name = _decode_node(name_node, source)

        symbols.append(Symbol(
            kind=kind,
            name=name,
            file=file,
            line_start=cap_node.start_point[0] + 1,
            line_end=cap_node.end_point[0] + 1,
            signature=_signature(source, cap_node),
        ))

    symbols.sort(key=lambda s: (s.line_start, s.line_end))
    return ExtractionResult(file=file, symbols=symbols, language=language_name, parse_error=False)


def _linear_walk(root_node, file: str, source: bytes, language_name: str) -> list[Symbol]:
    """Linear AST walk as a fallback if a query fails."""
    type_map = {
        "function_definition": ("function", "python"),
        "class_definition": ("class", "python"),
        "function_declaration": ("function", "javascript"),
        "class_declaration": ("class", "javascript"),
        "method_definition": ("method", "javascript"),
    }
    out: list[Symbol] = []

    def walk(node) -> None:
        if node.type in type_map:
            kind, expected_lang = type_map[node.type]
            if expected_lang != language_name:
                return
            name = _extract_name(node, source)
            if name:
                out.append(Symbol(
                    kind=kind,
                    name=name,
                    file=file,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_signature(source, node),
                ))
        for child in node.children:
            walk(child)

    walk(root_node)
    return out


def _extract_name(node, source: bytes) -> str:
    """Extract the identifier name from a function/class node."""
    for child in node.children:
        if child.type in ("identifier", "property_identifier"):
            return _decode_node(child, source)
    return ""


def extract_symbols_from_path(source_dir: Path, rel_path: str) -> ExtractionResult:
    """Extract symbols from a file on disk."""
    full_path = source_dir / rel_path
    source = _read_file(full_path)
    return extract_symbols(rel_path, source)


# =====================================================================
# Chunk boundaries (used by T-3.2 chunker)
# =====================================================================


@dataclass(frozen=True)
class ChunkBoundary:
    """A natural breakpoint for chunking extracted from tree-sitter."""

    line_start: int
    line_end: int
    kind: str        # "function" | "class" | "method"
    name: str = ""


def get_symbol_boundaries(source_dir: Path, rel_path: str) -> list[ChunkBoundary]:
    """Get natural chunk boundaries from a source file.

    These are used by the chunker to respect AST boundaries instead
    of splitting mid-function.
    """
    result = extract_symbols_from_path(source_dir, rel_path)
    return [
        ChunkBoundary(
            line_start=s.line_start,
            line_end=s.line_end,
            kind=s.kind,
            name=s.name,
        )
        for s in result.symbols
    ]


def is_treesitter_available() -> bool:
    """Whether tree-sitter is installed and at least Python grammar works."""
    return bool(_get_languages())
