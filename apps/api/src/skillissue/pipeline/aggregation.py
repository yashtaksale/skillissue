"""Analysis aggregation per ARCHITECTURE.md §7.5 and §7.7."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from skillissue.pipeline.coverage import compute_coverage
from skillissue.pipeline.hygiene import HygieneResult, check_all_hygiene
from skillissue.pipeline.orchestrator import AcquisitionMethod
from skillissue.pipeline.reporter import AnalysisReport, Finding, RepairConfig
from skillissue.pipeline.score import ScoredSignal, deduplicate_signals, filter_low_confidence, build_ranking
from skillissue.pipeline.sample import Chunk, ChunkBudget, chunk_repo


class AnalysisAggregator:
    """Aggregates pipeline results into a final AnalysisReport."""

    def __init__(
        self,
        repair_config: RepairConfig | None = None,
        max_findings: int = 50,
    ) -> None:
        self.repair_config = repair_config or RepairConfig()
        self.max_findings = max_findings

    def build_report(
        self,
        *,
        repo_full_name: str,
        ref: str | None,
        source_dir: Path | str,
        file_paths: list[str],
        manifest: dict | None,
        loc_total: int,
        loc_supported: int,
        hygiene_result: HygieneResult,
        scored_signals: list[ScoredSignal],
        acquisition_method: AcquisitionMethod,
        llm_used: bool = False,
        error: str | None = None,
    ) -> AnalysisReport:
        """Build the final analysis report.

        Args:
            repo_full_name: owner/repo string.
            ref: Branch or commit SHA.
            source_dir: Path to the extracted source.
            file_paths: All source files analyzed.
            manifest: Optional files.json manifest.
            loc_total: Total LOC in the repo.
            loc_supported: LOC in supported languages.
            hygiene_result: Hygiene check results.
            scored_signals: Deduplicated and scored signals.
            acquisition_method: How the source was acquired.
            llm_used: Whether LLM analysis was performed.
            error: Optional error message.

        Returns:
            Complete AnalysisReport.
        """
        coverage = compute_coverage(loc_total, loc_supported)

        # Filter low-confidence signals
        filtered = filter_low_confidence(scored_signals, min_confidence=0.3)

        # Build findings from top signals
        findings = self._build_findings(filtered)

        return AnalysisReport(
            repo_full_name=repo_full_name,
            ref=ref,
            files_scanned=len(file_paths),
            loc_total=loc_total,
            loc_supported=loc_supported,
            coverage=coverage.value,
            findings=findings,
            hygiene_flags=hygiene_result.flags,
            llm_used=llm_used,
            error=error,
        )

    def _build_findings(self, signals: list[ScoredSignal]) -> list[Finding]:
        """Convert scored signals to Finding objects."""
        ranked = build_ranking(signals, max_signals=self.max_findings)
        findings: list[Finding] = []
        for sig in ranked:
            priority = sig.priority
            findings.append(Finding(
                rule_id=sig.rule_id,
                category=sig.category,
                severity=sig.severity,
                confidence=sig.confidence,
                priority=priority,
                file_path=sig.file_path,
                line_start=sig.line_start,
                line_end=sig.line_end,
                message=f"{sig.tool}: {sig.rule_id}",
                snippet=sig.primary_snippet[:500],
                explanation="",  # filled by LLM or left empty
                fix="",  # filled by LLM or left empty
            ))
        return findings

    def chunk_for_llm(
        self,
        source_dir: Path | str,
        file_paths: list[str],
        context: str = "",
    ) -> list[Chunk]:
        """Prepare chunks for LLM analysis.

        Args:
            source_dir: Path to extracted source.
            file_paths: Source file paths to chunk.
            context: Summary context for the repo.

        Returns:
            List of Chunk objects ready for LLM processing.
        """
        return chunk_repo(source_dir, file_paths, context=context)
