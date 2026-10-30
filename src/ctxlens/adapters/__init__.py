"""Adapter registry and auto-detection.

`parse_session(path, agent)` is the one entry point the CLI uses. `agent`
may be an adapter name, ``auto`` (peek at the file and guess), or ``generic``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..models import ParsedSession
from . import claude, codex, generic

ADAPTERS = {
    "claude": claude,
    "codex": codex,
    "generic": generic,
}

AGENT_NAMES = tuple(ADAPTERS)


def detect_agent(path: Path) -> str:
    """Peek at the first parseable lines and guess the dialect."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in range(50):
                raw = fh.readline()
                if not raw:
                    break
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                keys = set(obj.keys())
                if "session_meta" == obj.get("type") or "payload" in keys and "ordinal" in keys:
                    return "codex"
                if "sessionId" in keys or "parentUuid" in keys or "isSidechain" in keys:
                    return "claude"
                if obj.get("type") == "summary" and "leafUuid" in keys:
                    return "claude"
    except OSError:
        pass
    return "generic"


def parse_session(path: Path, agent: str = "auto", warnings: List[str] | None =
    None) -> ParsedSession:
    """Parse one session file with the chosen (or detected) adapter."""
    if agent == "auto":
        agent = detect_agent(path)
    adapter = ADAPTERS.get(agent)
    if adapter is None:
        raise ValueError(f"unknown agent {agent!r}; known: {', '.join(AGENT_NAMES)}")
    warns: List[str] = []
    parsed = adapter.parse(path, warns)
    if warnings is not None:
        warnings.extend(warns)
    return parsed
