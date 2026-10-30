"""Adapter for Claude Code session logs.

Location: ``~/.claude/projects/<munged-cwd>/<session-uuid>.jsonl``

Format traits (observed across releases; everything here is read defensively):

- one JSON object per line, ``type`` in ``user`` / ``assistant`` / ``system``
  / ``summary`` (older builds compact into ``summary`` lines with ``leafUuid``)
- ``message.content`` is either a string or a list of typed items
  (``text`` / ``tool_use`` / ``tool_result`` / ``thinking``)
- assistant lines carry ``message.usage`` with real prompt sizes
  (``input_tokens`` + ``cache_creation_input_tokens`` + ``cache_read_input_tokens``)
- compaction shows up as a user line flagged ``isCompactSummary`` or a
  continuation message ("This session is being continued from a previous
  conversation...")

Anything not matching the shape of the day is warned about and skipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..models import (
    KIND_ASSISTANT,
    KIND_FILE_RESULT,
    KIND_REASONING,
    KIND_SUMMARY,
    KIND_SYSTEM,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    ParsedSession,
    UsagePoint,
)
from .base import content_text, first_str, iter_json_lines, make_block

_CONTINUATION_PREFIX = "this session is being continued from a previous conversation"
_FILE_RESULT_TOOLS = {"read", "view", "cat"}
_TOOL_RESULT_BUDGET_KEYS = ("content", "text", "output")


def _tool_result_text(content: Any, depth: int = 0) -> str:
    """tool_result payloads nest; flatten without trusting any one shape."""
    if depth > 4:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_tool_result_text(item, depth + 1) for item in content)
    if isinstance(content, dict):
        for key in _TOOL_RESULT_BUDGET_KEYS:
            if key in content:
                return _tool_result_text(content[key], depth + 1)
        return content_text(content)
    return "" if content is None else str(content)


def parse(path: Path, warnings: List[str]) -> ParsedSession:
    parsed = ParsedSession(agent="claude")
    tool_names: Dict[str, str] = {}  # tool_use_id -> tool name
    index = 0

    for lineno, obj in iter_json_lines(path, warnings):
        if obj is None:
            continue
        parsed.line_count += 1
        entry_type = first_str(obj, "type")
        timestamp = first_str(obj, "timestamp") or None

        if entry_type == "summary":
            text = first_str(obj, "summary")
            parsed.blocks.append(
                make_block(KIND_SUMMARY, text, index, name="summary", timestamp=timestamp)
            )
            parsed.compaction_marks.append((index, "summary"))
            index += 1
            continue

        message = obj.get("message")
        if not isinstance(message, dict):
            # system meta lines, queued-command stubs, API error stubs...
            if entry_type in ("system", "queued-command", "api-error"):
                text = content_text(obj.get("content") or message or obj.get("content"))
                if text.strip():
                    parsed.blocks.append(
                        make_block(KIND_SYSTEM, text, index, name=entry_type,
                                   timestamp=timestamp)
                    )
                    index += 1
            else:
                warnings.append(f"line {lineno}: unknown entry type {entry_type!r}, skipped")
            continue

        role = first_str(message, "role") or entry_type
        content = message.get("content")

        # --- compaction marks -------------------------------------------
        # Flagged summaries are explicit; continuation prose is the soft
        # signal older builds leave behind. Check the first text cheaply —
        # never flatten a full tool_result list just to sniff its opening.
        is_compact = bool(obj.get("isCompactSummary"))
        first_text = content if isinstance(content, str) else ""
        if not first_text and isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and first_str(item, "type") == "text":
                    first_text = first_str(item, "text")
                    break
        if is_compact or first_text.lower().startswith(_CONTINUATION_PREFIX):
            parsed.compaction_marks.append((index, "compact"))

        # --- usage (real prompt size at this turn) -----------------------
        usage = message.get("usage")
        if isinstance(usage, dict) and role == "assistant":
            total = sum(
                usage.get(k) or 0
                for k in (
                    "input_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                )
            )
            if total > 0:
                parsed.usage_points.append(
                    UsagePoint(tokens=int(total), real=True, label=f"line {lineno}",
                               timestamp=timestamp)
                )

        # --- content blocks ----------------------------------------------
        if isinstance(content, str):
            kind = KIND_USER if role == "user" else KIND_ASSISTANT
            if content.strip():
                parsed.blocks.append(
                    make_block(kind, content, index, name=role, timestamp=timestamp)
                )
                index += 1
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = first_str(item, "type")
                if item_type == "tool_use":
                    tool_id = first_str(item, "id")
                    name = first_str(item, "name")
                    if tool_id:
                        tool_names[tool_id] = name
                    parsed.blocks.append(
                        make_block(
                            KIND_TOOL_CALL,
                            content_text(item.get("input")),
                            index,
                            name=name or "tool",
                            timestamp=timestamp,
                        )
                    )
                    index += 1
                elif item_type == "tool_result":
                    tool_id = first_str(item, "tool_use_id")
                    name = tool_names.get(tool_id, "tool")
                    text = _tool_result_text(item.get("content"))
                    # toolUseResult.file carries the actual file payload on
                    # many builds — a stronger file-result signal than the
                    # tool name alone.
                    tur = obj.get("toolUseResult")
                    file_path = ""
                    if isinstance(tur, dict) and isinstance(tur.get("file"), dict):
                        file_path = first_str(tur["file"], "filePath")
                    kind = KIND_FILE_RESULT if (file_path or name.lower() in _FILE_RESULT_TOOLS) else KIND_TOOL_RESULT
                    if file_path:
                        name = file_path
                    parsed.blocks.append(
                        make_block(kind, text, index, name=name or "tool",
                                   timestamp=timestamp)
                    )
                    index += 1
                elif item_type == "thinking":
                    parsed.blocks.append(
                        make_block(KIND_REASONING, first_str(item, "thinking"), index,
                                   name="thinking", timestamp=timestamp)
                    )
                    index += 1
                elif item_type == "text":
                    text = first_str(item, "text")
                    if text.strip():
                        kind = KIND_USER if role == "user" else KIND_ASSISTANT
                        parsed.blocks.append(
                            make_block(kind, text, index, name=role, timestamp=timestamp)
                        )
                        index += 1
                else:
                    warnings.append(
                        f"line {lineno}: unknown content item type {item_type!r}, skipped"
                    )

        if not parsed.session_id:
            parsed.session_id = first_str(obj, "sessionId")
        if not parsed.cwd:
            parsed.cwd = first_str(obj, "cwd")

    return parsed
