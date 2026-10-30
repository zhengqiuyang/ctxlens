"""Deterministic token estimation.

ctxlens never calls a tokenizer library or an API. When a session file carries
real usage numbers (some agents log them), those are preferred upstream. This
module is the fallback — and the only engine behind per-block breakdowns,
which no agent reports.

The heuristic, stated honestly:

- Most BPE tokenizers average roughly one token per 4 ASCII characters
  (English prose and code both land close to this).
- CJK characters are far denser: one CJK char is commonly one token (sometimes
  two, rarely a fraction). We count each CJK char as one token — the
  conservative reading, and the right one for Chinese/Japanese/Korean content.
- Everything else (punctuation, digits, whitespace) folds into the /4 bucket.

Accuracy against real tokenizers is typically within ~25%. That is fine for
the question ctxlens answers — *which block ate the window* — and it is the
same number on every machine, every run, forever. Determinism beats precision
here; a report that shifts between runs cannot be baselined or diffed.
"""

from __future__ import annotations

import json
from typing import Any

# Ranges that tokenize densely (~1 token per char). Keep the list explicit and
# commented — "which ranges count as CJK" is part of the estimator's contract.
_CJK_RANGES = (
    (0x2E80, 0x2EFF),  # CJK Radicals Supplement
    (0x2F00, 0x2FDF),  # Kangxi Radicals
    (0x3000, 0x303F),  # CJK Symbols and Punctuation
    (0x3040, 0x30FF),  # Hiragana + Katakana
    (0x3100, 0x312F),  # Bopomofo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0x3400, 0x4DBF),  # CJK Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xAC00, 0xD7AF),  # Hangul Syllables
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0xFF00, 0xFF60),  # Fullwidth Forms
    (0x20000, 0x2FA1F),  # CJK Extensions B..F, Compatibility Supplement
)

_CHARS_PER_ASCII_TOKEN = 4.0


def _is_cjk(cp: int) -> bool:
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string. Same input, same output, always."""
    if not text or not text.strip():
        return 0
    cjk = 0
    other = 0
    for ch in text:
        if _is_cjk(ord(ch)):
            cjk += 1
        else:
            other += 1
    total = other / _CHARS_PER_ASCII_TOKEN + cjk
    if total < 1.0:
        # Whitespace or a stray character still costs the API round-trip a
        # nonzero floor once it reaches a real prompt; keep estimates honest.
        total = 1.0 if text.strip() else 0.0
    return int(round(total))


def estimate_object(obj: Any) -> int:
    """Estimate tokens for a JSON-serializable object (tool inputs, etc.)."""
    if obj is None:
        return 0
    try:
        text = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(obj)
    return estimate_tokens(text)
