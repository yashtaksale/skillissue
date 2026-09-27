"""Batch builder with nonce tags and closing-tag neutralization (T-4.3)."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

from skillissue.pipeline.sample.chunker import Chunk

# Limits per ARCHITECTURE.md §7.8
MAX_BATCH_CHUNKS = 3
MAX_BATCH_TOKENS = 8_000
CLOSING_TAG = "</chunk>"
OPENING_TAG = "<chunk>"


@dataclass(frozen=True)
class ChunkContext:
    """A chunk paired with the signals relevant to it."""

    chunk: Chunk
    signals: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Batch:
    """One LLM call: signals + chunks + a unique nonce."""

    nonce: str
    chunks: list[Chunk]
    signals: list[dict]
    total_tokens: int
    prompt_cached: bool = False
    cache_key: str = ""  # deterministic content hash (independent of nonce)


def _compute_hash(chunks, signals):
    """Deterministic content hash independent of the random nonce."""
    h = hashlib.sha256()
    for c in chunks:
        h.update(c.content.encode("utf-8"))
    for s in signals:
        h.update(s.get("signal_id", "").encode("utf-8"))
    return h.hexdigest()


def _nonce() -> str:
    """Generate a random nonce tag for closing-tag neutralization."""
    return secrets.token_hex(8)


def _neutralize(text: str, nonce: str) -> str:
    """Replace any literal chunk tags in source with the nonce-prefixed form.

    Prevents a malicious repo from breaking out of the rendering by
    injecting ``</chunk>`` or ``<chunk>`` into source code or comments.
    """
    if not text:
        return text
    return (
        text
        .replace(CLOSING_TAG, f"</chunk-{nonce}>")
        .replace(OPENING_TAG, f"<chunk-{nonce}>")
    )


def build_batches(
    chunk_contexts: list[ChunkContext],
    context: str = "",
    *,
    max_chunks: int = MAX_BATCH_CHUNKS,
    max_tokens: int = MAX_BATCH_TOKENS,
) -> list[Batch]:
    """Group chunks into LLM batches respecting token and count limits.

    Each batch gets a unique nonce; every chunk body has its literal
    ``</chunk>`` tags neutralized so source code cannot escape the prompt.
    """
    batches: list[Batch] = []
    current_chunks: list[Chunk] = []
    current_signals: list[dict] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current_chunks, current_signals, current_tokens
        if current_chunks:
            content_hash = _compute_hash(current_chunks, current_signals)
            batches.append(Batch(
                nonce=_nonce(),
                chunks=list(current_chunks),
                signals=list(current_signals),
                total_tokens=current_tokens,
                cache_key=content_hash,
            ))
        current_chunks = []
        current_signals = []
        current_tokens = 0

    for ctx in chunk_contexts:
        chunk_tokens = ctx.chunk.estimated_tokens
        signals_tokens = 0
        new_signals = list(ctx.signals)

        # Rough token estimate for the signal block
        for sig in ctx.signals:
            signals_tokens += len(sig.get("message", "")) // 4
            signals_tokens += len(sig.get("snippet", "")) // 4
            signals_tokens += 20  # overhead per signal for JSON structure

        would_overflow = (
            current_chunks
            and (current_tokens + chunk_tokens + signals_tokens) > max_tokens
        )
        would_exceed_chunk_limit = len(current_chunks) >= max_chunks

        if would_overflow or would_exceed_chunk_limit:
            flush()

        current_chunks.append(ctx.chunk)
        current_signals.extend(new_signals)
        current_tokens += chunk_tokens + signals_tokens

    flush()
    return batches


def render_batch_prompt(batch: Batch, context: str = "") -> str:
    """Render the user prompt for a batch with nonce-tagged, neutralized chunks."""
    # Build signals block
    sig_lines: list[str] = []
    for s in batch.signals:
        sig_lines.append(
            f"- signal_id={s.get('signal_id', '?')}"
            f"  rule={s.get('rule_id', '?')}"
            f"  file={s.get('file_path', s.get('file', '?'))}"
            f"  line={s.get('line_start', '?')}-{s.get('line_end', '?')}"
            f"  severity={s.get('severity', '?')}"
            f"  message={s.get('message', '')}"
        )
    signals_block = "\n".join(sig_lines) if sig_lines else "(no scanner signals for this batch)"

    # Build chunks block with nonce tags
    tag_open = f"<chunk-{batch.nonce}>"
    tag_close = f"</chunk-{batch.nonce}>"
    chunk_parts: list[str] = []
    for c in batch.chunks:
        # Neutralize any literal chunk tags inside the source
        body = _neutralize(c.content, batch.nonce)
        chunk_parts.append(f"{tag_open}\n{body}\n{tag_close}")
    chunks_block = "\n\n".join(chunk_parts)

    from skillissue.pipeline.llm.schema import USER_PROMPT_TEMPLATE

    return USER_PROMPT_TEMPLATE.format(
        signals_block=signals_block,
        chunks_block=chunks_block,
    )
