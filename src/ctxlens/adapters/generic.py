"""Generic JSONL fallback adapter.

For session logs from tools ctxlens does not know yet — or tools that changed
their format since breakfast. It maps what it recognizes by common key names
(``role`` / ``type`` / ``event`` for shape, ``content`` / ``text`` /
``message`` for body) and buckets the rest as ``other``.

The generic adapter is deliberately boring: it will never be as sharp as a
native adapter, but it makes every JSONL session log at least *lookable*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..models import (
    KIND_ASSISTANT,
    KIND_OTHER,
    KIND_REASONING,
    KIND_SYSTEM,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    ParsedSession,
)
from .base import content_text, first_str, iter_json_lines, make_block

_ROLE_KINDS = {
    "system": KIND_SYSTEM,
    "developer": KIND_SYSTEM,
    "user": KIND_USER,
    "human": KIND_USER,
    "assistant": KIND_ASSISTANT,
    "ai": KIND_ASSISTANT,
}

_TYPE_HINT_KINDS = {
    "tool_call": KIND_TOOL_CALL,
    "tool_use": KIND_TOOL_CALL,
    "function_call": KIND_TOOL_CALL,
    "tool_result": KIND_TOOL_RESULT,
    "function_call_output": KIND_TOOL_RESULT,
    "tool": KIND_TOOL_RESULT,
    "thinking": KIND_REASONING,
    "reasoning": KIND_REASONING,
    "summary": KIND_SYSTEM,
}


def _guess_text(obj: Dict[str, Any]) -> str:
    """Best-effort body extraction from unknown shapes."""
    for key in ("content", "text", "message", "body", "output", "arguments"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict):
            inner = content_text(val)
            if inner.strip():
                return inner
        elif isinstance(val, list):
            inner = content_text(val)
            if inner.strip():
                return inner
    return ""


def parse(path: Path, warnings: List[str]) -> ParsedSession:
    parsed = ParsedSession(agent="generic")
    index = 0

    for lineno, obj in iter_json_lines(path, warnings):
        if obj is None:
            continue
        parsed.line_count += 1

        # Unwrap a single level of nesting ({...,"message": {...}} is common).
        inner: Dict[str, Any] = obj
        nested = obj.get("message")
        if isinstance(nested, dict) and ("content" in nested or "role" in nested):
            inner = {**obj, **nested}

        shape = first_str(inner, "role", "event")
        entry_type = first_str(inner, "type")
        timestamp = first_str(obj, "timestamp") or None

        if shape in _ROLE_KINDS:
            kind = _ROLE_KINDS[shape]
            name = shape
        elif entry_type in _TYPE_HINT_KINDS:
            kind = _TYPE_HINT_KINDS[entry_type]
            name = first_str(inner, "name") or entry_type
        elif entry_type:
            kind = KIND_OTHER
            name = entry_type
        else:
            kind = KIND_OTHER
            name = "entry"

        # Tool calls/results may carry a tool name next to the body.
        name = first_str(inner, "tool", "tool_name", "name") or name

        text = _guess_text(inner)
        if not text.strip() and kind is KIND_OTHER:
            continue  # pure metadata line — nothing to X-ray
        parsed.blocks.append(
            make_block(kind, text, index, name=name, timestamp=timestamp)
        )
        index += 1

        if not parsed.session_id:
            for key in ("sessionId", "session_id", "id", "conversationId"):
                if isinstance(obj.get(key), str) and obj[key]:
                    parsed.session_id = obj[key]
                    break

    return parsed
