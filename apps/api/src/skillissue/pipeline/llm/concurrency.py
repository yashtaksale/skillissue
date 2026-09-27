"""Concurrency controller with dead-line support (T-4.7)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_CONCURRENT = 4
DEFAULT_DEADLINE_SECONDS = 120.0


@dataclass(frozen=True)
class ConcurrencyConfig:
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS


class ConcurrencyController:
    """Limits parallel LLM calls and enforces a wall-clock deadline."""

    def __init__(self, config: ConcurrencyConfig | None = None) -> None:
        self._config = config or ConcurrencyConfig()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        self._completed = 0
        self._failed = 0
        self._cancelled = False

    async def call(self, coro: Any) -> Any:
        """Run a coroutine under semaphore and deadline."""
        async with self._semaphore:
            if self._cancelled:
                raise asyncio.CancelledError("Scan was cancelled")
            deadline = time.monotonic() + self._config.deadline_seconds
            try:
                result = await asyncio.wait_for(coro, timeout=self._config.deadline_seconds)
                self._completed += 1
                return result
            except asyncio.TimeoutError:
                self._failed += 1
                raise
            except asyncio.CancelledError:
                self._cancelled = True
                raise

    def cancel(self) -> None:
        """Cancel all in-flight and future calls."""
        self._cancelled = True

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def failed(self) -> int:
        return self._failed
