"""Shared adapter plumbing: tolerant line iteration, previews, cleanup.

The first law of adapters: a session file is another program's log, written by
another team, changing under another release cadence. ctxlens reads it the way
you read a stranger's handwriting — take what is legible, note what is not,
never stop the line.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .. import tokens as tok
from ..models import PREVIEW_CHARS, Block

_WS_RUN = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    """One safe line of context for a block: no control chars, no newlines."""
    if not isinstance(text, str):
        text = str(text)
    text = _CTRL.sub("", text)
    text = _WS_RUN.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def iter_json_lines(
    path: Path, warnings: List[str]
) -> Iterator[Tuple[int, Optional[Dict[str, Any]]]]:
    """Yield (line_number, obj) for parseable lines; warn and continue on bad
    ones. A broken line is data about the file, not an error in the run."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except ValueError:
                warnings.append(f"line {lineno}: not valid JSON, skipped")
                yield lineno, None
                continue
            if not isinstance(obj, dict):
                warnings.append(f"line {lineno}: not a JSON object, skipped")
                yield lineno, None
                continue
            yield lineno, obj


def content_text(content: Any) -> str:
    """Flatten a message `content` (string or item list) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "output", "input", "thinking"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
                else:
                    if "type" in item:
                        parts.append(f"[{item['type']}]")
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def make_block(kind: str, text: str, index: int, name: str = "", timestamp:
    Optional[str] = None, real_tokens: Optional[int] = None) -> Block:
    """Build a Block with an estimated size; adapters pass real sizes through
    `real_tokens` only when the log reports one for this exact block."""
    tokens = real_tokens if real_tokens is not None else tok.estimate_tokens(text)
    return Block(
        kind=kind,
        tokens=tokens,
        index=index,
        name=name,
        preview=clean_preview(text),
        timestamp=timestamp,
    )


def first_str(obj: Dict[str, Any], *keys: str) -> str:
    """First present, string-valued key among *keys* — empty string if none."""
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str) and val:
            return val
    return ""
