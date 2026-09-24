"""Exceptions raised by the URL parser."""
from __future__ import annotations


class URLError(Exception):
    """Base exception for URL parsing failures."""


class UnsupportedHostError(URLError):
    """Raised when the URL host is not github.com."""


class InvalidFormatError(URLError):
    """Raised when the URL or shorthand cannot be parsed."""


class UnsafeRepoError(URLError):
    """Raised when owner/repo contain unsafe characters or patterns."""


class ControlCharacterError(URLError):
    """Raised when the input contains control characters."""


class TooLongError(URLError):
    """Raised when the input exceeds the maximum allowed length."""


class ReservedNameError(URLError):
    """Raised when owner starts/ends with '-' or repo is '.' or '..'."""
