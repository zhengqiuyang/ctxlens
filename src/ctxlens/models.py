"""Data model shared by adapters, the analyzer and the renderers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Block kinds — the vocabulary of the whole tool. Adapters map raw entries
# into these; the analyzer buckets them; renderers color them.
KIND_SYSTEM = "system"
KIND_USER = "user_text"
KIND_ASSISTANT = "assistant_text"
KIND_TOOL_CALL = "tool_call"
KIND_TOOL_RESULT = "tool_result"
KIND_FILE_RESULT = "file_result"
KIND_REASONING = "reasoning"
KIND_SUMMARY = "summary"
KIND_OTHER = "other"

ALL_KINDS = (
    KIND_SYSTEM,
    KIND_USER,
    KIND_ASSISTANT,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_FILE_RESULT,
    KIND_REASONING,
    KIND_SUMMARY,
    KIND_OTHER,
)

# Analyzer buckets: which block kinds roll up into which composition slot.
BUCKETS: Dict[str, tuple] = {
    "system": (KIND_SYSTEM, KIND_SUMMARY),
    "user": (KIND_USER,),
    "assistant": (KIND_ASSISTANT, KIND_REASONING),
    "tool_calls": (KIND_TOOL_CALL,),
    "tool_results": (KIND_TOOL_RESULT, KIND_FILE_RESULT),
    "other": (KIND_OTHER,),
}
BUCKET_ORDER = ("system", "user", "assistant", "tool_calls", "tool_results", "other")

PREVIEW_CHARS = 72


@dataclass
class Block:
    """One context-occupying chunk in session order."""

    kind: str
    tokens: int
    index: int  # position within the session (0-based, session order)
    name: str = ""  # tool name for calls/results, role label otherwise
    preview: str = ""
    timestamp: Optional[str] = None
    # Set by compaction forensics: this block was before the cut and is gone.
    dropped_by_compaction: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "tokens": self.tokens,
            "index": self.index,
            "name": self.name,
            "preview": self.preview,
        }
        if self.timestamp is not None:
            d["timestamp"] = self.timestamp
        if self.dropped_by_compaction:
            d["dropped_by_compaction"] = True
        return d


@dataclass
class UsagePoint:
    """Context size at one turn, from real usage numbers when available."""

    tokens: int
    real: bool  # True: reported by the agent; False: estimated by ctxlens
    label: str = ""
    timestamp: Optional[str] = None


@dataclass
class CompactionEvent:
    """A detected context cut: compaction, continuation or summary marker."""

    index: int  # block index where the cut happens
    kind: str  # "compact" | "continuation" | "summary"
    before_tokens: int = 0
    after_tokens: int = 0
    dropped_tokens: int = 0
    dropped_top: List[Block] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "before_tokens": self.before_tokens,
            "after_tokens": self.after_tokens,
            "dropped_tokens": self.dropped_tokens,
            "dropped_top": [b.to_dict() for b in self.dropped_top],
        }


@dataclass
class ParsedSession:
    """What an adapter produces from one session file."""

    agent: str
    blocks: List[Block] = field(default_factory=list)
    usage_points: List[UsagePoint] = field(default_factory=list)
    compaction_marks: List[tuple] = field(default_factory=list)  # (index, kind)
    session_id: str = ""
    model: str = ""
    context_window: Optional[int] = None
    cwd: str = ""
    line_count: int = 0


@dataclass
class SessionReport:
    """The full analysis of one session — input to every renderer."""

    source: str
    agent: str
    session_id: str = ""
    model: str = ""
    context_window: Optional[int] = None
    blocks: List[Block] = field(default_factory=list)
    composition: Dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    # True when composition buckets were scaled to match a real usage number.
    scaled_to_real: bool = False
    # Whole-file estimate (every block, pre-compaction history included).
    file_total_tokens: int = 0
    # Block index where the last compaction cut sits; None if never compacted.
    cut_index: Optional[int] = None
    top_offenders: List[Block] = field(default_factory=list)
    curve: List[UsagePoint] = field(default_factory=list)
    compactions: List[CompactionEvent] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    line_count: int = 0

    @property
    def latest_context_tokens(self) -> int:
        """Best estimate of the live context size at the end of the session."""
        if self.curve:
            return self.curve[-1].tokens
        return self.total_tokens

    def window_fraction(self) -> Optional[float]:
        if not self.context_window:
            return None
        return self.latest_context_tokens / self.context_window

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "agent": self.agent,
            "session_id": self.session_id,
            "model": self.model,
            "context_window": self.context_window,
            "line_count": self.line_count,
            "total_tokens": self.total_tokens,
            "latest_context_tokens": self.latest_context_tokens,
            "window_fraction": (
                round(self.window_fraction(), 4)
                if self.window_fraction() is not None
                else None
            ),
            "scaled_to_real": self.scaled_to_real,
            "file_total_tokens": self.file_total_tokens,
            "cut_index": self.cut_index,
            "composition": {k: self.composition.get(k, 0) for k in BUCKET_ORDER},
            "top_offenders": [b.to_dict() for b in self.top_offenders],
            "curve": [
                {"tokens": p.tokens, "real": p.real, "label": p.label}
                for p in self.curve
            ],
            "compactions": [c.to_dict() for c in self.compactions],
            "warnings": list(self.warnings),
        }
