"""Coverage decision logic."""
from __future__ import annotations

from enum import StrEnum


class CoverageKind(StrEnum):
    """Coverage levels for analysis."""

    FULL = "full"
    PARTIAL = "partial"
    REDUCED_COVERAGE = "reduced_coverage"
    HYGIENE_ONLY = "hygiene_only"


# Thresholds per ARCHITECTURE.md §7.3
_LOC_PARTIAL_THRESHOLD = 500_000
_FILES_PARTIAL_THRESHOLD = 10_000
_RATIO_THRESHOLD = 0.5


def decide(
    loc_total: int,
    loc_supported: int,
    loc_analyzed: int,
    file_count: int,
) -> CoverageKind:
    """Determine the coverage level for a scan.

    Args:
        loc_total: Total non-blank lines across all files (including unknown langs).
        loc_supported: Non-blank lines in recognized/supported languages.
        loc_analyzed: Non-blank lines in files that passed all filters.
        file_count: Number of files that passed all filters.

    Returns:
        CoverageKind enum value.
    """
    if loc_supported == 0:
        return CoverageKind.HYGIENE_ONLY

    if loc_analyzed > _LOC_PARTIAL_THRESHOLD or file_count > _FILES_PARTIAL_THRESHOLD:
        return CoverageKind.PARTIAL

    ratio = loc_supported / loc_total if loc_total > 0 else 1.0
    if ratio < _RATIO_THRESHOLD:
        return CoverageKind.REDUCED_COVERAGE

    return CoverageKind.FULL


def compute_coverage(
    loc_total: int,
    loc_supported: int,
    file_count: int = 0,
    loc_analyzed: int = 0,
) -> str:
    """Convenience wrapper: returns CoverageKind as a string.

    Used by AnalysisAggregator to set report.coverage.
    """
    return decide(loc_total, loc_supported, loc_analyzed, file_count).value
