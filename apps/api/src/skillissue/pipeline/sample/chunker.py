"""Source code chunking for LLM-safe payloads."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Chunk budget defaults per ARCHITECTURE.md §7.6
_DEFAULT_MAX_FILES = 200
_DEFAULT_MAX_TOKENS = 150_000  # fit within 200K with  headroom
_DEFAULT_MIN_FILE_TOKENS = 50
_DEFAULT_CONTEXT_TOKENS = 50


@dataclass
class Chunk:
    """A single chunk of files to send to the LLM."""

    chunk_id: int
    files: list[str]
    total_lines: int
    total_bytes: int
    estimated_tokens: int
    context: str = ""


@dataclass
class ChunkBudget:
    """Budget for chunk generation."""

    max_files: int = _DEFAULT_MAX_FILES
    max_tokens: int = _DEFAULT_MAX_TOKENS
    min_file_tokens: int = _DEFAULT_MIN_FILE_TOKENS
    context_tokens: int = _DEFAULT_CONTEXT_TOKENS


def _read_file(path: Path) -> str:
    """Read a source file, returning its content as a string."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.2))


def chunk_repo(
    source_dir: Path | str,
    file_paths: list[str],
    *,
    context: str = "",
    budget: ChunkBudget | None = None,
) -> list[Chunk]:
    """Chunk a list of files into LLM-safe payloads.

    Strategy: sort files by LOC descending (biggest first), pack into chunks
    greedily respecting budget limits.

    Args:
        source_dir: Root directory of the extracted repo.
        file_paths: List of relative file paths to chunk.
        context: Summary context prepended to each chunk.
        budget: Chunk budget configuration.

    Returns:
        List of Chunk objects.
    """
    if budget is None:
        budget = ChunkBudget()

    source_dir = Path(source_dir)
    context_tokens = budget.context_tokens if context else 0

    # Build (path, tokens, lines, bytes) tuples
    file_data: list[tuple[str, int, int, int]] = []
    for rel_path in file_paths:
        full_path = source_dir / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue
        content = _read_file(full_path)
        tokens = _estimate_tokens(content)
        if tokens < budget.min_file_tokens:
            continue
        lines = content.count("\n") + 1 if content else 0
        size = full_path.stat().st_size
        file_data.append((rel_path, tokens, lines, size))

    # Sort descending by LOC (tokens proxy) — biggest files first
    file_data.sort(key=lambda x: x[1], reverse=True)

    chunks: list[Chunk] = []
    current_files: list[str] = []
    current_tokens = context_tokens
    current_lines = 0
    current_bytes = 0

    for rel_path, tokens, lines, size in file_data:
        if len(current_files) >= budget.max_files:
            chunks.append(Chunk(
                chunk_id=len(chunks),
                files=current_files,
                total_lines=current_lines,
                total_bytes=current_bytes,
                estimated_tokens=current_tokens,
                context=context,
            ))
            current_files = []
            current_tokens = context_tokens
            current_lines = 0
            current_bytes = 0

        if current_tokens + tokens > budget.max_tokens:
            if current_files:
                chunks.append(Chunk(
                    chunk_id=len(chunks),
                    files=current_files,
                    total_lines=current_lines,
                    total_bytes=current_bytes,
                    estimated_tokens=current_tokens,
                    context=context,
                ))
                current_files = []
                current_tokens = context_tokens
                current_lines = 0
                current_bytes = 0
            else:
                # Single file exceeds budget — include it anyway
                pass

        current_files.append(rel_path)
        current_tokens += tokens
        current_lines += lines
        current_bytes += size

    if current_files:
        chunks.append(Chunk(
            chunk_id=len(chunks),
            files=current_files,
            total_lines=current_lines,
            total_bytes=current_bytes,
            estimated_tokens=current_tokens,
            context=context,
        ))

    return chunks
