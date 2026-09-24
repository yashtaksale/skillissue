"""Token estimation utility for chunk budget accounting."""
from __future__ import annotations


# Conservative estimate: ~3.2 characters per token (English text average)
# Used when no tokenizer is available. Within 15% of real counts per ARCHITECTURE.md §7.6.
_CHARS_PER_TOKEN = 3.2


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a simple character-based heuristic. For production accuracy,
    swap in a real tokenizer (e.g., Anthropic's count_tokens API).

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count (always >= 1 for non-empty text, 0 for empty).
    """
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def estimate_tokens_batch(texts: list[str]) -> int:
    """Estimate total tokens for a list of text strings."""
    return sum(estimate_tokens(t) for t in texts)


class TokenBudget:
    """Tracks token usage against a budget."""

    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens
        self.used = 0

    def add(self, text: str) -> bool:
        """Try to add text to the budget. Returns True if within budget."""
        tokens = estimate_tokens(text)
        if self.used + tokens > self.max_tokens:
            return False
        self.used += tokens
        return True

    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used)

    def __repr__(self) -> str:
        return f"TokenBudget(used={self.used}, max={self.max_tokens}, remaining={self.remaining()})"
