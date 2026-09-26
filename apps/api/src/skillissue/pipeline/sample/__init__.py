"""Sampling and chunking pipeline (Phase 3).

T-3.1: Tree-sitter extraction (in analyze/extractor.py)
T-3.2: Chunker with overlap, context headers, 2k–6k targets
T-3.3: File scorer with risk-path, entrypoint, test, signal bonuses
T-3.4: Greedy selector with diversity constraints + forced signal inclusion
T-3.5: Token estimator and budget (in sample/token_estimator.py)
T-3.6: Secret redaction pass
T-3.7: CLI `sample <dir>` command
"""
from __future__ import annotations

from skillissue.pipeline.analyze.extractor import (
    ChunkBoundary,
    ExtractionResult,
    extract_symbols_from_path,
    get_symbol_boundaries,
)
from skillissue.pipeline.sample.chunker import (
    Chunk,
    ChunkBudget,
    chunk_repo,
)
from skillissue.pipeline.sample.token_estimator import (
    TokenBudget,
    estimate_tokens,
)

__all__ = [
    # extractor
    "ChunkBoundary",
    "ExtractionResult",
    "extract_symbols_from_path",
    "get_symbol_boundaries",
    # chunker
    "Chunk",
    "ChunkBudget",
    "chunk_repo",
    # token estimator
    "TokenBudget",
    "estimate_tokens",
]
