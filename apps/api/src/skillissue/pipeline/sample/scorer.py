"""File scoring for the greedy selector (T-3.3).

Scores each file based on:
  - risk_path_score (auth, sql, payment, admin...)
  - entrypoint detection (main.py, app.py, index.ts...)
  - test/fixture detection (lower priority)
  - scanner signal presence (files with known bugs get boosted)
  - LLM value heuristic (files with tree-sitter symbols score higher)

Higher scores = files selected first by the greedy selector (T-3.4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# =====================================================================
# Path-based scoring
# =====================================================================

_RISK_HIGH = re.compile(
    r"(?:^|/)(?:auth|login|logout|session|token|jwt|oauth|password|passwd|secret|"
    r"crypto|payment|billing|stripe|admin|upload|download|sql|query|db|database|"
    r"orm|middleware|permission|acl|rbac|webhook|shell|exec|process)(?:$|[./])",
    re.IGNORECASE,
)
_RISK_MED = re.compile(
    r"(?:^|/)(?:api|route|router|controller|handler|view|endpoint|server|config|"
    r"settings|template|render|deserial|serial|socket|queue|worker)(?:$|[./])",
    re.IGNORECASE,
)

_ENTRYPOINT_NAMES = {
    "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py",
    "server.js", "server.ts", "index.js", "index.ts", "app.js", "app.ts",
    "cli.py", "main.go", "cmd.go",
}

_TEST_DIRS = frozenset({
    "test", "tests", "__tests__", "spec", "e2e", "integration", "fixtures",
})
_TEST_FILE_PATTERNS = [
    re.compile(r"^test_.*\.py$", re.IGNORECASE),
    re.compile(r".*_test\.py$", re.IGNORECASE),
    re.compile(r".*\.test\.(js|jsx|ts|tsx)$", re.IGNORECASE),
    re.compile(r".*\.spec\.(js|jsx|ts|tsx)$", re.IGNORECASE),
]
_GENERATED_PATTERNS = [
    re.compile(r"\.min\.[a-z]+$", re.IGNORECASE),
    re.compile(r"generated", re.IGNORECASE),
    re.compile(r"Code generated", re.IGNORECASE),
    re.compile(r"DO NOT EDIT", re.IGNORECASE),
    re.compile(r"auto[-_]?generated", re.IGNORECASE),
]


def risk_path_score(path: str) -> float:
    """Score a file path for security risk. 0.0–1.0."""
    if _RISK_HIGH.search(path):
        return 1.0
    if _RISK_MED.search(path):
        return 0.5
    return 0.0


def is_entrypoint(path: str) -> bool:
    """Whether the file is an application entrypoint."""
    name = Path(path).name
    if name in _ENTRYPOINT_NAMES:
        return True
    parts = [p.lower() for p in Path(path).parts]
    return "pages" in parts and "api" in parts or \
           "app" in parts and "api" in parts or \
           "routes" in parts


def is_test(path: str) -> bool:
    """Whether the file is a test/fixture (lower priority for sampling)."""
    p = Path(path)
    name = p.name
    for pat in _TEST_FILE_PATTERNS:
        if pat.match(name):
            return True
    parts = {part.casefold() for part in p.parts}
    return bool(parts & _TEST_DIRS)


def is_generated(path: str) -> bool:
    """Whether the file appears auto-generated."""
    name = Path(path).name
    for pat in _GENERATED_PATTERNS:
        if pat.search(name):
            return True
    return False


def supported_language(path: str) -> bool:
    """Whether the file is in a language tree-sitter can parse."""
    from skillissue.pipeline.analyze.extractor import _EXT_TO_LANG
    return Path(path).suffix.lower() in _EXT_TO_LANG


# =====================================================================
# FileScore — the scored representation used by T-3.4
# =====================================================================


@dataclass
class FileScore:
    """Score and metadata for a single source file."""

    path: str
    lines: int
    estimated_tokens: int
    risk_score: float = 0.0
    is_test: bool = False
    is_entrypoint: bool = False
    is_generated: bool = False
    symbol_count: int = 0
    base_score: float = 0.0
    final_score: float = 0.0
    selection_reason: str = ""

    def compute(self) -> None:
        """Compute final_score from base heuristics."""
        self.base_score = 0.0
        reasons: list[str] = []

        # Risk path is the biggest signal
        if self.risk_score >= 1.0:
            self.base_score += 0.40
            reasons.append("high-risk path")
        elif self.risk_score >= 0.5:
            self.base_score += 0.20
            reasons.append("medium-risk path")

        # Entrypoint files are valuable
        if self.is_entrypoint:
            self.base_score += 0.15
            reasons.append("entrypoint")

        # More symbols = more complexity = more analysis value
        if self.symbol_count >= 20:
            self.base_score += 0.15
            reasons.append("high complexity")
        elif self.symbol_count >= 5:
            self.base_score += 0.10
            reasons.append("moderate complexity")

        # Larger files tend to have more logic
        if self.lines >= 500:
            self.base_score += 0.10
            reasons.append("large file")
        elif self.lines >= 100:
            self.base_score += 0.05

        # Test files are lower priority
        if self.is_test:
            self.base_score -= 0.30
            reasons.append("test file")

        # Generated files are lowest priority
        if self.is_generated:
            self.base_score -= 0.50
            reasons.append("generated")

        self.final_score = max(0.0, min(1.0, self.base_score))
        self.selection_reason = ", ".join(reasons) if reasons else "general coverage"


# =====================================================================
# File scorer entrypoint (T-3.3)
# =====================================================================


def score_files(
    file_paths: list[str],
    file_lines: dict[str, int],
    *,
    signal_paths: list[str] | None = None,
    source_dir: Path | str | None = None,
    use_tree_sitter: bool = True,
) -> list[FileScore]:
    """Score all files for the greedy selector.

    Args:
        file_paths: Relative file paths in the repo.
        file_lines: {path: LOC} mapping.
        signal_paths: Paths of files that have scanner signals (boost these).
        source_dir: Root directory (for tree-sitter symbol counting).
        use_tree_sitter: Whether to count symbols via tree-sitter.

    Returns:
        Sorted list of FileScore objects (highest first).
    """
    signal_set = set(signal_paths or [])
    scores: list[FileScore] = []

    for path in file_paths:
        risk = risk_path_score(path)
        scores.append(FileScore(
            path=path,
            lines=file_lines.get(path, 0),
            estimated_tokens=file_lines.get(path, 0) // 3,  # rough estimate
            risk_score=risk,
            is_test=is_test(path),
            is_entrypoint=is_entrypoint(path),
            is_generated=is_generated(path),
        ))

    # Count tree-sitter symbols if available
    if use_tree_sitter:
        from skillissue.pipeline.analyze.extractor import (
            extract_symbols_from_path,
            is_treesitter_available,
        )
        if is_treesitter_available() and source_dir:
            source = Path(source_dir)
            for fs in scores:
                if fs.is_generated or fs.is_test:
                    continue
                try:
                    result = extract_symbols_from_path(source, fs.path)
                    fs.symbol_count = len(result.symbols)
                except Exception:
                    pass

    # Boost files that have scanner signals
    for fs in scores:
        if fs.path in signal_set:
            fs.final_score = min(1.0, fs.final_score + 0.30)
            fs.selection_reason += ", has signals"

    # Compute final scores
    for fs in scores:
        fs.compute()

    scores.sort(key=lambda s: (-s.final_score, s.path))
    return scores


def score_file(
    path: str,
    file_lines: dict[str, int],
    *,
    has_signal: bool = False,
    source_dir: Path | str | None = None,
) -> FileScore:
    """Score a single file."""
    signal_paths = [path] if has_signal else None
    results = score_files([path], file_lines, signal_paths=signal_paths, source_dir=source_dir)
    return results[0] if results else FileScore(path=path, lines=file_lines.get(path, 0), estimated_tokens=0)
