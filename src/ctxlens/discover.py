"""Find agent session logs on this machine.

Discovery roots (overridable via ``CTXLENS_HOME`` for tests and portable
installs):

- Claude Code: ``~/.claude/projects/**/*.jsonl``
- Codex CLI:   ``~/.codex/sessions/**/*.jsonl``

Only file metadata is read here — names, sizes, mtimes. Session content is
touched by adapters alone, and only after the user picks a file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

#: Cap per-agent walk so a machine with thousands of sessions stays snappy.
MAX_FILES_PER_AGENT = 500


@dataclass
class SessionRef:
    path: Path
    agent: str
    size: int
    mtime: float

    def label(self) -> str:
        stamp = self.path.stat().st_mtime
        import datetime

        when = datetime.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M")
        size_k = self.size / 1024
        size_s = f"{size_k:.0f}K" if size_k >= 1 else f"{self.size}B"
        return f"{when}  {self.agent:<8} {size_s:>8}  {self.path.name}"


def _home() -> Path:
    override = os.environ.get("CTXLENS_HOME")
    if override:
        return Path(override)
    return Path.home()


def _walk(root: Path, pattern: str, agent: str, found: List[SessionRef]) -> None:
    if not root.is_dir():
        return
    count = 0
    try:
        for path in sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime,
                           reverse=True):
            try:
                stat = path.stat()
            except OSError:
                continue
            if not stat.st_size:
                continue
            found.append(SessionRef(path=path, agent=agent, size=stat.st_size,
                                    mtime=stat.st_mtime))
            count += 1
            if count >= MAX_FILES_PER_AGENT:
                break
    except OSError:
        return


def discover(agent: Optional[str] = None) -> List[SessionRef]:
    """All known session logs, newest first. ``agent`` narrows to one tool."""
    home = _home()
    agents = [agent] if agent and agent != "auto" else ["claude", "codex"]
    found: List[SessionRef] = []
    for name in agents:
        if name == "claude":
            _walk(home / ".claude" / "projects", "*.jsonl", "claude", found)
        elif name == "codex":
            _walk(home / ".codex" / "sessions", "*.jsonl", "codex", found)
    found.sort(key=lambda ref: ref.mtime, reverse=True)
    return found


def latest(agent: Optional[str] = None) -> Optional[SessionRef]:
    refs = discover(agent)
    return refs[0] if refs else None
