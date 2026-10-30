"""Adapter for Codex CLI session logs.

Location: ``~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl``

Format traits (verified against live rollout files, 2026 builds):

- one JSON object per line: ``type`` in ``session_meta`` / ``response_item``
  / ``event_msg`` / ``turn_context`` / ``world_state`` / ...
- ``session_meta.payload``: ``context_window`` (the budget!), ``cwd``,
  ``base_instructions``, ``model_provider``, ``cli_version``
- ``response_item.payload``: typed items — ``message`` (role
  developer/user/assistant with ``content`` items), ``function_call``,
  ``function_call_output``, ``reasoning``, ...
- ``event_msg.payload``: progress and bookkeeping events; token accounting
  appears as ``token_count`` events when the build reports them
- developer-role messages are the system side of the conversation

Codex ships schema changes constantly; unknown payload types are counted and
skipped, never fatal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import (
    KIND_ASSISTANT,
    KIND_FILE_RESULT,
    KIND_OTHER,
    KIND_REASONING,
    KIND_SYSTEM,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    ParsedSession,
    UsagePoint,
)
from .base import content_text, first_str, iter_json_lines, make_block

_FILE_RESULT_TOOLS = {"read_file", "read", "view", "cat", "open"}


def _flatten_content_items(content: Any) -> str:
    """Codex content items: {"type": "input_text"|"output_text"|"text", "text": ...}."""
    return content_text(content)


def _token_count_from_event(payload: Dict[str, Any]) -> Optional[int]:
    """Extract a prompt-size number from a token_count event, if any.

    Builds differ: some log ``info.total_token_usage``, some
    ``info.last_token_usage``. We take the input-side total when present.
    """
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    for holder_key in ("total_token_usage", "last_token_usage"):
        holder = info.get(holder_key)
        if not isinstance(holder, dict):
            continue
        total = holder.get("input_tokens") or holder.get("total_tokens") or 0
        if total:
            return int(total)
    return None


def parse(path: Path, warnings: List[str]) -> ParsedSession:
    parsed = ParsedSession(agent="codex")
    index = 0
    call_names: Dict[str, str] = {}  # call_id -> tool name

    for lineno, obj in iter_json_lines(path, warnings):
        if obj is None:
            continue
        parsed.line_count += 1
        entry_type = first_str(obj, "type")
        timestamp = first_str(obj, "timestamp") or None
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if entry_type == "session_meta":
            parsed.session_id = first_str(payload, "session_id") or first_str(payload, "id")
            parsed.cwd = first_str(payload, "cwd")
            window = payload.get("context_window")
            if isinstance(window, (int, float)) and window > 0:
                parsed.context_window = int(window)
            base = payload.get("base_instructions")
            if isinstance(base, str) and base.strip():
                parsed.blocks.append(
                    make_block(KIND_SYSTEM, base, index, name="base_instructions",
                               timestamp=timestamp)
                )
                index += 1
            elif isinstance(base, list):
                text = content_text(base)
                if text.strip():
                    parsed.blocks.append(
                        make_block(KIND_SYSTEM, text, index, name="base_instructions",
                                   timestamp=timestamp)
                    )
                    index += 1
            continue

        if entry_type == "turn_context":
            if not parsed.model:
                parsed.model = first_str(payload, "model")
            continue

        if entry_type == "event_msg":
            event = first_str(payload, "type")
            if event == "token_count":
                total = _token_count_from_event(payload)
                if total:
                    parsed.usage_points.append(
                        UsagePoint(tokens=total, real=True, label=f"line {lineno}",
                                   timestamp=timestamp)
                    )
            elif "compact" in event:
                parsed.compaction_marks.append((index, "compact"))
            continue

        if entry_type == "response_item":
            item_type = first_str(payload, "type")
            role = first_str(payload, "role")

            if item_type == "message":
                text = _flatten_content_items(payload.get("content"))
                if role == "developer":
                    kind, name = KIND_SYSTEM, "developer"
                elif role == "user":
                    kind, name = KIND_USER, "user"
                elif role == "assistant":
                    kind, name = KIND_ASSISTANT, "assistant"
                else:
                    kind, name = KIND_OTHER, role or "message"
                if text.strip():
                    parsed.blocks.append(
                        make_block(kind, text, index, name=name, timestamp=timestamp)
                    )
                    index += 1
            elif item_type == "function_call":
                name = first_str(payload, "name") or "tool"
                call_id = first_str(payload, "call_id") or first_str(payload, "id")
                if call_id:
                    call_names[call_id] = name
                args = payload.get("arguments")
                text = args if isinstance(args, str) else content_text(args)
                parsed.blocks.append(
                    make_block(KIND_TOOL_CALL, text, index, name=name, timestamp=timestamp)
                )
                index += 1
            elif item_type == "function_call_output":
                call_id = first_str(payload, "call_id")
                name = call_names.get(call_id, call_id or "tool")
                output = payload.get("output")
                text = output if isinstance(output, str) else content_text(output)
                kind = (
                    KIND_FILE_RESULT if name.lower() in _FILE_RESULT_TOOLS else KIND_TOOL_RESULT
                )
                parsed.blocks.append(
                    make_block(kind, text, index, name=name, timestamp=timestamp)
                )
                index += 1
            elif item_type == "reasoning":
                summary = payload.get("summary")
                text = content_text(summary) if summary is not None else first_str(payload, "text")
                if text.strip():
                    parsed.blocks.append(
                        make_block(KIND_REASONING, text, index, name="reasoning",
                                   timestamp=timestamp)
                    )
                    index += 1
            else:
                warnings.append(
                    f"line {lineno}: unknown response_item type {item_type!r}, skipped"
                )
            continue

        # world_state, additional_tools, configuration_update, ... — noted,
        # skipped, counted.
        warnings.append(f"line {lineno}: unhandled entry type {entry_type!r}, skipped")

    return parsed
