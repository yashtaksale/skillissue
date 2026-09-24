"""Scanner domain — signal models, severity mapping, masking, snippet building."""
from __future__ import annotations

from skillissue.domain.scanner.models import RawSignal
from skillissue.domain.scanner.severity_map import map_severity
from skillissue.domain.scanner.masker import mask_secret, mask_secret_short
from skillissue.domain.scanner.snippet import build_snippet

__all__ = [
    "RawSignal",
    "map_severity",
    "mask_secret",
    "mask_secret_short",
    "build_snippet",
]
