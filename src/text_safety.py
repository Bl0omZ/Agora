"""Text cleanup helpers for model-visible output."""

from __future__ import annotations

import re


_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_RE = re.compile(r"<think\b[^>]*>.*$", flags=re.IGNORECASE | re.DOTALL)
_THINK_CLOSE_RE = re.compile(r"</think>", flags=re.IGNORECASE)


def strip_hidden_reasoning(content: str) -> str:
    """Remove hidden reasoning blocks before content is shown, stored, or exported."""
    without_closed = _THINK_BLOCK_RE.sub("", content or "")
    without_unclosed = _UNCLOSED_THINK_RE.sub("", without_closed)
    return _THINK_CLOSE_RE.sub("", without_unclosed).strip()
