"""Cost tracker: pricing table, per-scan cap, daily ledger (T-4.6)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import date

from skillissue.pipeline.llm.adapter import TokenBudgetExceeded

# Pricing per 1M tokens (USD, list prices as of 2025)
PRICING_TABLE: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-haiku-4": {"input": 0.25, "output": 1.25},
}

DEFAULT_MODEL = "claude-sonnet-4"
COST_PER_SCAN_CAP = 0.25  # USD — stop calling LLM above this
DAILY_LEDGER_CAP = 100.0  # USD — daily global budget


@dataclass
class UsageRecord:
    """One LLM call's usage."""

    model: str
    input_tokens: int
    output_tokens: int
    cost: float


class CostTracker:
    """Tracks token usage and cost for a scan, with daily ledger."""

    def __init__(
        self,
        scan_cap: float = COST_PER_SCAN_CAP,
        daily_cap: float = DAILY_LEDGER_CAP,
        ledger: dict[date, float] | None = None,
    ) -> None:
        self._scan_cap = scan_cap
        self._daily_cap = daily_cap
        self._ledger: dict[date, float] = dict(ledger or {})
        self._scan_usage: list[UsageRecord] = []
        self._scan_cost = 0.0
        self._lock = threading.Lock()

    # ── public ───────────────────────────────────────────────────────

    def record(self, *, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record one LLM call. Returns the cost of this call.

        Raises ``TokenBudgetExceeded`` if this call would exceed caps.
        """
        cost = self._compute_cost(model, input_tokens, output_tokens)
        today = date.today()

        with self._lock:
            projected_scan = self._scan_cost + cost
            projected_daily = self._ledger.get(today, 0.0) + cost

            if projected_scan > self._scan_cap:
                raise TokenBudgetExceeded(
                    f"Per-scan budget ${self._scan_cap:.2f} would be exceeded "
                    f"(projected ${projected_scan:.4f})"
                )
            if projected_daily > self._daily_cap:
                raise TokenBudgetExceeded(
                    f"Daily budget ${self._daily_cap:.2f} would be exceeded "
                    f"(projected ${projected_daily:.4f})"
                )

            self._scan_usage.append(UsageRecord(model, input_tokens, output_tokens, cost))
            self._scan_cost = projected_scan
            self._ledger[today] = projected_daily

        return cost

    def check_can_afford(self, *, model: str, estimated_tokens: int) -> bool:
        """Pre-flight check: can we afford one more call?"""
        if model not in PRICING_TABLE:
            model = DEFAULT_MODEL
        price = PRICING_TABLE[model]
        # Assume output = 30% of estimated tokens as a heuristic
        est_output = max(1, int(estimated_tokens * 0.3))
        cost = self._compute_cost(model, estimated_tokens, est_output)
        today = date.today()
        with self._lock:
            return (
                self._scan_cost + cost <= self._scan_cap
                and self._ledger.get(today, 0.0) + cost <= self._daily_cap
            )

    @property
    def scan_cost(self) -> float:
        with self._lock:
            return self._scan_cost

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(r.input_tokens + r.output_tokens for r in self._scan_usage)

    @property
    def usage(self) -> list[UsageRecord]:
        with self._lock:
            return list(self._scan_usage)

    def daily_total(self, day: date | None = None) -> float:
        with self._lock:
            return self._ledger.get(day or date.today(), 0.0)

    def ledger_snapshot(self) -> dict[str, float]:
        with self._lock:
            return {d.isoformat(): c for d, c in self._ledger.items()}

    # ── private ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        price = PRICING_TABLE.get(model) or PRICING_TABLE[DEFAULT_MODEL]
        input_cost = (input_tokens / 1_000_000) * price["input"]
        output_cost = (output_tokens / 1_000_000) * price["output"]
        return input_cost + output_cost


class _AsyncLedgerProxy:
    """Async-compatible wrapper for the ledger dict used in tests."""

    def __init__(self) -> None:
        self._data: dict[date, float] = {}
        self._lock = asyncio.Lock()

    async def get(self, day: date) -> float:
        return self._data.get(day, 0.0)

    async def add(self, day: date, amount: float) -> None:
        self._data[day] = self._data.get(day, 0.0) + amount

    def snapshot(self) -> dict[str, float]:
        return {d.isoformat(): c for d, c in self._data.items()}
