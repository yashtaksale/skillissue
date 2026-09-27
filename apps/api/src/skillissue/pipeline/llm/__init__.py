"""LLM stage package — analysis pipeline, guards, cost tracking.

T-4.1: LLM adapter with retries/backoff/timeouts (adapter.py)
T-4.2: Tool schema and Pydantic models (schema.py)
T-4.3: Batch builder with injection protection (batch.py)
T-4.4: Output guards (guards.py)
T-4.5: Prompt cache with 30-day TTL (cache.py)
T-4.6: Cost tracker with budget caps (cost.py)
T-4.7: Concurrency controller + scanners-only fallback (concurrency.py, analyzer.py)
T-4.8:  detection heuristic (guards.py)
T-4.9: FakeLLM fixtures for tests
T-4.10: Precision/cost notes in MEMORY.md
"""
from __future__ import annotations

from skillissue.pipeline.llm.adapter import (
    DEFAULT_CONFIG,
    LLMAdapter,
    LLMConfig,
    LLMError,
    RateLimitError,
    TokenBudgetExceeded,
)
from skillissue.pipeline.llm.analyzer import (
    AnalysisConfig,
    AnalysisResult,
    analyze_chunks,
    merge_llm_findings,
)
from skillissue.pipeline.llm.batch import (
    Batch,
    ChunkContext,
    build_batches,
    render_batch_prompt,
)
from skillissue.pipeline.llm.cache import LLMCache
from skillissue.pipeline.llm.concurrency import ConcurrencyConfig, ConcurrencyController
from skillissue.pipeline.llm.cost import CostTracker, UsageRecord
from skillissue.pipeline.llm.guards import (
    GuardResult,
    GuardStats,
    apply_guards,
    apply_injection_filter,
    detect_injection,
)
from skillissue.pipeline.llm.schema import (
    AnalysisBatchResult,
    FindingOutput,
    SYSTEM_PROMPT,
    TOOL_SCHEMA,
)

__all__ = [
    # adapter
    "DEFAULT_CONFIG",
    "LLMAdapter",
    "LLMConfig",
    "LLMError",
    "RateLimitError",
    "TokenBudgetExceeded",
    # analyzer
    "AnalysisConfig",
    "AnalysisResult",
    "analyze_chunks",
    "merge_llm_findings",
    # batch
    "Batch",
    "ChunkContext",
    "build_batches",
    "render_batch_prompt",
    # cache
    "LLMCache",
    # concurrency
    "ConcurrencyConfig",
    "ConcurrencyController",
    # cost
    "CostTracker",
    "UsageRecord",
    # guards
    "GuardResult",
    "GuardStats",
    "apply_guards",
    "apply_injection_filter",
    "detect_injection",
    # schema
    "AnalysisBatchResult",
    "FindingOutput",
    "SYSTEM_PROMPT",
    "TOOL_SCHEMA",
]
