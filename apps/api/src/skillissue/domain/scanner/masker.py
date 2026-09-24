"""Secret masking utilities.

No more than 6 visible characters of any secret should ever leave the
scanner container (ARCHITECTURE.md §7.4).
"""
from __future__ import annotations


def mask_secret(value: str) -> str:
    """Mask a secret so at most 6 characters are visible.

    For strings longer than 6 characters the first 4 and the last 2 are
    preserved; everything between them is replaced with ``"•"``.

    Examples::

        >>> mask_secret("AKIAIOSFODNN7EXAMPLE")
        'AKIA••••••••••••••MPLE'
        >>> mask_secret("abcdefg")
        'abcd••••••••g'
        >>> mask_secret("")
        ''
    """
    length = len(value)
    if length <= 6:
        return mask_secret_short(value)
    return value[:4] + "•" * (length - 6) + value[-2:]


def mask_secret_short(value: str) -> str:
    """Mask a short secret (length ≤ 6).

    The first 2 characters are preserved; the rest are masked.  An empty
    string or single-character string is returned unchanged (nothing to
    mask that is *not* already exposed).

    Examples::

        >>> mask_secret_short("abcd")
        'ab••'
        >>> mask_secret_short("X")
        'X'
        >>> mask_secret_short("")
        ''
    """
    length = len(value)
    if length <= 2:
        return value
    return value[:2] + "•" * (length - 2)


__all__ = ["mask_secret", "mask_secret_short"]
