"""Async LLM adapter with retries, backoff, and timeouts (T-4.1)."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam

from skillissue.pipeline.llm.schema import SYSTEM_PROMPT, TOOL_SCHEMA

# ── Config ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LLMConfig:
    """Parameters for a single LLM call."""

    model: str = "claude-sonnet-4"
    max_tokens: int = 4096
    temperature: float = 0.2
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_base_delay: float = 1.0
    retry_max_delay: float = 16.0
    tools: list[dict] = field(default_factory=lambda: [TOOL_SCHEMA])
    tool_choice: dict | None = None  # None = auto, {"type": "tool", "name": ...} = force


DEFAULT_CONFIG = LLMConfig(tool_choice={"type": "tool", "name": "report_findings"})

# ── Retry logic ──────────────────────────────────────────────────────


class LLMError(Exception):
    """Base error for LLM failures."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class RateLimitError(LLMError):
    """429 — retry with backoff."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message, retryable=True)
        self.retry_after = retry_after


class TokenBudgetExceeded(Exception):
    """Raised when the per-scan token budget is exhausted."""

    pass


# ── Adapter ──────────────────────────────────────────────────────────


class LLMAdapter:
    """Thin async wrapper around the Anthropic SDK.

    Handles retries with exponential backoff, timeouts, and cost tracking.
    """

    def __init__(
        self,
        api_key: str,
        *,
        config: LLMConfig | None = None,
        cost_tracker: Any = None,
        fake_responses: list[Any] | None = None,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key) if api_key else None
        self._config = config or DEFAULT_CONFIG
        self._cost_tracker = cost_tracker
        self._fake_responses = fake_responses  # None = real API, [] = stub, [x] = recorded
        self._fake_index = 0

    # ── public ───────────────────────────────────────────────────────

    async def analyze_batch(
        self,
        messages: list[MessageParam],
        *,
        config: LLMConfig | None = None,
    ) -> Message:
        """Send a batch of messages and return the raw Anthropic Message.

        Retries on 429/5xx up to ``max_retries`` times.
        """
        cfg = config or self._config
        last_err: Exception | None = None

        for attempt in range(1 + cfg.max_retries):
            try:
                start = time.monotonic()
                if self._fake_responses is not None:
                    # An explicit fake_responses list was provided (even empty = stub)
                    response = await self._fake_call(messages, cfg)
                else:
                    response = await asyncio.wait_for(
                        self._real_call(messages, cfg),
                        timeout=cfg.timeout_seconds,
                    )
                elapsed = time.monotonic() - start

                if self._cost_tracker:
                    self._cost_tracker.record(
                        model=cfg.model,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                    )
                return response

            except RateLimitError as exc:
                delay = exc.retry_after or _backoff_delay(
                    attempt, cfg.retry_base_delay, cfg.retry_max_delay
                )
                last_err = exc
                await _sleep(delay)

            except LLMError as exc:
                if not exc.retryable:
                    raise
                last_err = exc
                await _sleep(_backoff_delay(attempt, cfg.retry_base_delay, cfg.retry_max_delay))

            except TimeoutError:
                last_err = LLMError(f"LLM call timed out after {cfg.timeout_seconds}s")
                await _sleep(_backoff_delay(attempt, cfg.retry_base_delay, cfg.retry_max_delay))

        raise last_err or LLMError("All retries exhausted")

    async def analyze_batch_with_tools(
        self,
        user_content: str,
        *,
        config: LLMConfig | None = None,
    ) -> dict:
        """High-level helper: build messages, call LLM, extract tool output.

        Returns dict with:
          - ``findings``: list of finding dicts
          - ``raw_response``: full text from LLM
          - ``usage``: input/output token counts
        """
        cfg = config or self._config
        messages: list[MessageParam] = [
            {"role": "user", "content": user_content},
        ]
        response = await self.analyze_batch(messages, config=cfg)

        findings: list[dict] = []
        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text += block.text
            elif block.type == "tool_use":
                if block.name == "report_findings":
                    findings.extend(block.input.get("findings", []))

        return {
            "findings": findings,
            "raw_response": raw_text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    # ── private ──────────────────────────────────────────────────────

    async def _real_call(self, messages: list[MessageParam], cfg: LLMConfig) -> Message:
        if not self._client:
            raise LLMError("No API key configured — use fake mode for testing", retryable=False)
        try:
            return await self._client.messages.create(
                model=cfg.model,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=cfg.tools,
                tool_choice=cfg.tool_choice,
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            if status == 429:
                retry_after = _parse_retry_after(exc)
                raise RateLimitError(str(exc), retry_after=retry_after) from exc
            if status and status >= 500:
                raise LLMError(f"LLM server error {status}: {exc}") from exc
            raise LLMError(f"LLM error: {exc}", retryable=False) from exc

    async def _fake_call(self, messages: list[MessageParam], cfg: LLMConfig) -> Message:
        """Return a recorded fake response for testing."""
        from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

        if not self._fake_responses:
            usage = Usage(input_tokens=100, output_tokens=50)
            text_block = TextBlock(type="text", text="No findings.", text_block_type="text")
            return Message(
                id="fake_msg_1",
                content=[text_block],
                model=cfg.model,
                role="assistant",
                stop_reason="end_turn",
                type="message",
                usage=usage,
            )

        resp = self._fake_responses[self._fake_index % len(self._fake_responses)]
        self._fake_index += 1
        if asyncio.iscoroutine(resp):
            resp = await resp
        if callable(resp):
            result = resp(messages, cfg)
            if asyncio.iscoroutine(result):
                result = await result
            resp = result

        # Accept dict responses and convert to Message
        if isinstance(resp, dict):
            findings = resp.get("findings", [])
            usage = Usage(
                input_tokens=resp.get("usage", {}).get("input_tokens", 100),
                output_tokens=resp.get("usage", {}).get("output_tokens", 50),
            )
            content: list = []
            if raw_text := resp.get("raw_response"):
                content.append(TextBlock(type="text", text=raw_text, text_block_type="text"))
            if findings:
                content.append(ToolUseBlock(
                    id="tool_use_1",
                    name="report_findings",
                    input={"findings": findings},
                    type="tool_use",
                ))
            return Message(
                id="fake_msg",
                content=content,
                model=cfg.model,
                role="assistant",
                stop_reason="tool_use",
                type="message",
                usage=usage,
            )

        return resp


# ── Helpers ─────────────────────────────────────────────────────────


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    """Exponential backoff with jitter."""
    delay = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(0, delay * 0.3)
    return delay + jitter


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _parse_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header value if available."""
    headers = getattr(exc, "response", None) or {}
    for attr in ("headers", "_headers"):
        hdr = getattr(exc, attr, {})
        val = hdr.get("retry-after") or hdr.get("Retry-After")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None
