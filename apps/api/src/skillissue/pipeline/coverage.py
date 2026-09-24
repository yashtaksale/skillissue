"""Coverage decision logic."""
from __future__ import annotations

from enum import StrEnum


class CoverageKind(StrEnum):
    """Coverage levels for analysis."""

    FULL = "full"
    PARTIAL = "partial"
    REDUCED_COVERAGE = "reduced_coverage"
    HYGIENE_ONLY = "hygiene_only"


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
    # No supported LOC at all → hygiene only
    if loc_supported == 0:
        return CoverageKind.HYGIENE_ONLY

    # Too much code for full analysis
    if loc_analyzed > _LOC_PARTIAL_THRESHOLD or file_count > _FILES_PARTIAL_THRESHOLD:
        return CoverageKind.PARTIAL

    # Insufficient supported LOC relative to total
    ratio = loc_supported / loc_total if loc_total > 0 else 1.0
    if ratio < _RATIO_THRESHOLD:
        return CoverageKind.REDUCED_COVERAGE

    return CoverageKind.FULL
