"""LLM analysis pipeline (T-4.3 through T-4.10).

Orchestrates:
  1. Build batches from chunks + signals (T-4.3)
  2. Call LLM with retries, concurrency, and deadline (T-4.1, T-4.7)
  3. Validate outputs with guards (T-4.4)
  4. Detect and filter  (T-4.8)
  5. Track costs and respect budgets (T-4.6)
  6. Use prompt cache on repeated chunks (T-4.5)
  7. Support scanners-only fallback on failure (T-4.7)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from skillissue.pipeline.llm.adapter import LLMAdapter, LLMConfig, LLMError
from skillissue.pipeline.llm.batch import ChunkContext, build_batches, render_batch_prompt
from skillissue.pipeline.llm.cache import LLMCache
from skillissue.pipeline.llm.concurrency import ConcurrencyConfig, ConcurrencyController
from skillissue.pipeline.llm.cost import CostTracker, TokenBudgetExceeded
from skillissue.pipeline.llm.guards import GuardStats, apply_guards, apply_injection_filter
from skillissue.pipeline.llm.schema import FindingOutput, TOOL_SCHEMA
from skillissue.pipeline.score import ScoredSignal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisConfig:
    """Top-level analysis configuration."""

    model: str = "claude-sonnet-4"
    max_chunks_per_batch: int = 3
    max_tokens_per_batch: int = 8_000
    max_concurrent: int = 4
    deadline_seconds: float = 120.0
    scan_cost_cap: float = 0.25
    enable_cache: bool = True
    fake_mode: bool = True
    max_batches: int = 20


@dataclass
class AnalysisResult:
    """Complete result of running the LLM analysis pipeline."""

    findings: list[FindingOutput] = field(default_factory=list)
    guard_stats: GuardStats | None = None
    cost_tracker: CostTracker | None = None
    batches_processed: int = 0
    batches_failed: int = 0
    scanners_only: bool = False
    error: str | None = None
    cached_count: int = 0

    @property
    def total_cost(self) -> float:
        return self.cost_tracker.scan_cost if self.cost_tracker else 0.0

    @property
    def total_tokens(self) -> int:
        return self.cost_tracker.total_tokens if self.cost_tracker else 0


def _signals_to_dicts(signals: list[ScoredSignal]) -> list[dict]:
    """Convert ScoredSignal objects to the dict format the batch builder expects."""
    result = []
    for s in signals:
        result.append({
            "signal_id": s.signal_id,
            "rule_id": s.rule_id,
            "category": s.category,
            "severity": s.severity,
            "confidence": s.confidence,
            "file_path": s.file_path,
            "file": s.file_path,
            "line_start": s.line_start,
            "line_end": s.line_end,
            "message": f"Scanner detected: {s.rule_id} ({s.severity})",
            "snippet": s.primary_snippet,
            "tool": s.tool,
        })
    return result


async def analyze_chunks(
    chunks: list[Any],
    signals: list[ScoredSignal],
    source_files: dict[str, int] | None = None,
    *,
    config: AnalysisConfig | None = None,
    api_key: str = "",
    adapter: LLMAdapter | None = None,
    cost_tracker: CostTracker | None = None,
    cache: LLMCache | None = None,
) -> AnalysisResult:
    """Run LLM analysis on a set of chunks with all guards and budget checks.

    This is the main entry point for the LLM stage (T-4.3–T-4.10).

    Returns an AnalysisResult. If the LLM is unavailable or the budget
    is exhausted, returns an empty result with ``scanners_only=True``.
    """
    cfg = config or AnalysisConfig()
    tracker = cost_tracker or CostTracker(scan_cap=cfg.scan_cost_cap)
    # Use `is None` (not truthiness) so an empty-but-valid cache is reused
    llm_cache = cache if cache is not None else (LLMCache() if cfg.enable_cache else None)
    controller = ConcurrencyController(ConcurrencyConfig(
        max_concurrent=cfg.max_concurrent,
        deadline_seconds=cfg.deadline_seconds,
    ))

    if adapter is None:
        adapter = LLMAdapter(api_key=api_key or "", cost_tracker=tracker)
    llm_config = LLMConfig(
        model=cfg.model,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "report_findings"},
    )

    signal_dicts = _signals_to_dicts(signals)
    valid_signal_ids = {s["signal_id"] for s in signal_dicts}
    contexts = [ChunkContext(chunk=c, signals=signal_dicts) for c in chunks]
    batches = build_batches(
        chunk_contexts=contexts,
        max_chunks=cfg.max_chunks_per_batch,
        max_tokens=cfg.max_tokens_per_batch,
    )
    if len(batches) > cfg.max_batches:
        batches = batches[: cfg.max_batches]

    all_findings: list[FindingOutput] = []
    guard_stats = GuardStats()
    batches_processed = 0
    batches_failed = 0
    cached_count = 0

    async def _process(batch: Any) -> None:
        nonlocal all_findings, guard_stats, batches_processed, batches_failed, cached_count

        # Check cache first
        if llm_cache is not None and batch.cache_key:
            cached = llm_cache.get(batch.cache_key)
            if cached is not None:
                cached_count += 1
                all_findings.extend(cached)
                return

        # Budget check
        if not tracker.check_can_afford(model=cfg.model, estimated_tokens=batch.total_tokens):
            return

        # LLM call
        try:
            prompt = render_batch_prompt(batch)
            raw = await controller.call(
                adapter.analyze_batch_with_tools(prompt, config=llm_config)
            )

            # Record cost
            if tracker is not None:
                usage = raw.get("usage", {})
                try:
                    tracker.record(
                        model=cfg.model,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                    )
                except TokenBudgetExceeded:
                    return

            batch_findings = raw.get("findings", [])

            parsed: list[FindingOutput] = []
            for f in batch_findings:
                try:
                    parsed.append(FindingOutput(**f))
                except Exception:
                    guard_stats.record_drop("schema_error")
                    continue

            clean, injection = apply_injection_filter(parsed)
            if injection:
                guard_stats.injection_suspected = True

            validated, gstats = apply_guards(
                [f.model_dump() for f in clean],
                valid_signal_ids=valid_signal_ids,
                source_files=source_files or {},
            )

            all_findings.extend(validated)
            guard_stats.total_input += len(batch_findings)
            guard_stats.total_output += len(validated)
            guard_stats.total_dropped += gstats.total_dropped
            guard_stats.injection_suspected = (
                guard_stats.injection_suspected or gstats.injection_suspected
            )
            for reason, count in gstats.drop_reasons.items():
                guard_stats.drop_reasons[reason] = (
                    guard_stats.drop_reasons.get(reason, 0) + count
                )
            for field, count in gstats.fields_modified.items():
                guard_stats.fields_modified[field] = (
                    guard_stats.fields_modified.get(field, 0) + count
                )

            # Store in cache
            if llm_cache is not None and batch.cache_key:
                llm_cache.set(batch.cache_key, validated)

            batches_processed += 1

        except (LLMError, TimeoutError, TokenBudgetExceeded) as exc:
            batches_failed += 1
            logger.warning("Batch failed: %s", exc)
        except Exception as exc:
            batches_failed += 1
            logger.warning("Unexpected batch error: %s", exc)

    await asyncio.gather(*[_process(b) for b in batches], return_exceptions=False)

    if batches_processed == 0 and not all_findings:
        return AnalysisResult(
            scanners_only=True,
            error="LLM analysis unavailable (all batches failed or budget exhausted)",
            cost_tracker=tracker,
            guard_stats=guard_stats,
            batches_failed=batches_failed,
        )

    return AnalysisResult(
        findings=all_findings,
        guard_stats=guard_stats,
        cost_tracker=tracker,
        batches_processed=batches_processed,
        batches_failed=batches_failed,
        cached_count=cached_count,
    )


def merge_llm_findings(
    scanner_signals: list[ScoredSignal],
    llm_findings: list[FindingOutput],
) -> list[ScoredSignal]:
    """Merge LLM findings back into the scored signal list (T-5.1 precursor)."""
    llm_map: dict[str, FindingOutput] = {f.signal_id: f for f in llm_findings}

    merged: list[ScoredSignal] = []
    for sig in scanner_signals:
        llm = llm_map.get(sig.signal_id)
        if llm is not None:
            merged.append(ScoredSignal(
                signal_id=sig.signal_id,
                rule_id=sig.rule_id,
                category=llm.category,
                tool=sig.tool,
                severity=llm.severity,
                confidence=llm.confidence,
                file_path=llm.file_path,
                line_start=llm.line_start,
                line_end=llm.line_end,
                occurrences=sig.occurrences,
                locations=sig.locations,
                primary_snippet=sig.primary_snippet,
                risk_score=llm.confidence * 0.5 + sig.risk_score * 0.5,
            ))
        else:
            merged.append(sig)
    return merged
