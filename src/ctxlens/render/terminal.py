"""Terminal renderer: the session X-ray in ANSI, zero dependencies.

Color is decoration; the layout must read clean with it stripped (piped,
NO_COLOR, dumb terminal). Numbers are formatted deterministically — no
locale, no float noise.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Dict, List

from ..models import BUCKET_ORDER, SessionReport

# --- ANSI plumbing -----------------------------------------------------------

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

_BUCKET_COLORS: Dict[str, str] = {
    "system": "\x1b[35m",        # magenta
    "user": "\x1b[36m",          # cyan
    "assistant": "\x1b[34m",     # blue
    "tool_calls": "\x1b[33m",    # yellow
    "tool_results": "\x1b[31m",  # red — the usual suspects
    "other": "\x1b[90m",         # grey
}

_SPARK = "▁▂▃▄▅▆▇█"


def _enable_windows_ansi() -> None:
    # Modern Windows consoles accept ANSI after any os.system("").
    if os.name == "nt":  # pragma: no cover - platform guard
        os.system("")


def _use_color(color_flag: bool) -> bool:
    if not color_flag:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_pct(fraction: float) -> str:
    return f"{fraction * 100:.1f}%"


def _sparkline(points: List[int], width: int = 48) -> str:
    if not points:
        return ""
    if len(points) > width:
        step = len(points) / width
        sampled = [points[int(i * step)] for i in range(width)]
    else:
        sampled = points
    lo, hi = min(sampled), max(sampled)
    span = max(1, hi - lo)
    chars = []
    for value in sampled:
        level = int((value - lo) / span * (len(_SPARK) - 1))
        chars.append(_SPARK[level])
    return "".join(chars)


def _bar(fraction: float, width: int, fill: str, empty: str, color: str) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * width))
    body = fill * filled + empty * (width - filled)
    return f"{color}{body}{_RESET}" if color else body


def render_terminal(report: SessionReport, top: int = 10, color: bool = True) -> str:
    use_color = _use_color(color)
    lines: List[str] = []
    out = lines.append

    def paint(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if use_color else text

    if os.name == "nt":  # pragma: no cover - platform guard
        _enable_windows_ansi()

    # --- header ------------------------------------------------------------
    title = "ctxlens — session X-ray"
    out(paint(title, _BOLD))
    meta = f"agent: {report.agent}"
    if report.model:
        meta += f"   model: {report.model}"
    if report.session_id:
        sid = report.session_id if len(report.session_id) <= 24 else report.session_id[:24] + "…"
        meta += f"   session: {sid}"
    out(paint(meta, _DIM))
    out(paint(f"source: {report.source}", _DIM))
    out("")

    # --- budget --------------------------------------------------------------
    fraction = report.window_fraction()
    if fraction is not None:
        pct = _fmt_pct(fraction)
        alarm = fraction >= 0.8
        bar = _bar(fraction, 40, "█", "░", "\x1b[31m" if alarm else "\x1b[32m" if use_color else "")
        out(f"context window  {bar}  {pct}  ({_fmt_int(report.latest_context_tokens)}"
            f" / {_fmt_int(report.context_window)})")
        if alarm:
            out(paint("⚠ 80%+ of the window is spent. Compaction is coming.", "\x1b[31m" + _BOLD))
        out("")

    # --- composition ---------------------------------------------------------
    out(paint("composition (live context)", _BOLD))
    if report.scaled_to_real:
        out(paint("  buckets scaled to the agent's own usage report", _DIM))
    total = max(1, report.total_tokens)
    width = shutil.get_terminal_size((88, 24)).columns or 88
    bar_width = max(24, min(40, width - 44))
    for bucket in BUCKET_ORDER:
        bucket_tokens = report.composition.get(bucket, 0)
        if bucket_tokens <= 0:
            continue
        share = bucket_tokens / total
        bar = _bar(share, bar_width, "█", "·", _BUCKET_COLORS.get(bucket, "") if use_color else "")
        label = bucket.replace("_", " ")
        out(f"  {label:<14}{bar}  {_fmt_pct(share).rjust(6)}  {_fmt_int(bucket_tokens).rjust(10)}")
    out(f"  {'total':<14}{'':<{bar_width}}  {'100.0%'.rjust(6)}  "
        f"{_fmt_int(report.total_tokens).rjust(10)}")
    if report.file_total_tokens > report.total_tokens:
        out(paint(
            f"  (file holds {_fmt_int(report.file_total_tokens)} estimated tokens in total;"
            f" pre-compaction history is marked, not counted)",
            _DIM,
        ))
    out("")

    # --- top offenders ---------------------------------------------------------
    if report.top_offenders:
        out(paint(f"top offenders (largest blocks, top {min(top, len(report.top_offenders))})", _BOLD))
        shown = report.top_offenders[:top]
        name_width = max(1, *(len(b.name) for b in shown)) if shown else 1
        for rank, block in enumerate(shown, 1):
            kind_label = block.kind.replace("_", " ")
            line = (f"  {rank:>2}. {_fmt_int(block.tokens).rjust(8)}  "
                    f"{kind_label:<12} {block.name[:name_width]}")
            out(line)
            if block.preview:
                out(paint(f"      └ {block.preview}", _DIM))
        out("")

    # --- bloat curve -----------------------------------------------------------
    if report.curve:
        out(paint("bloat curve (context size across the session)", _BOLD))
        points = [p.tokens for p in report.curve]
        real_marks = sum(1 for p in report.curve if p.real)
        flavor = "real usage" if real_marks == len(points) and real_marks > 0 else "estimated"
        out(f"  {_sparkline(points)}  {flavor}")
        out(f"  min {_fmt_int(min(points))}   max {_fmt_int(max(points))}   "
            f"{len(points)} points")
        out("")

    # --- compaction forensics ----------------------------------------------------
    if report.compactions:
        out(paint("compaction forensics", _BOLD))
        for event in report.compactions:
            out(f"  cut #{event.index} [{event.kind}]  before {_fmt_int(event.before_tokens)}"
                f"  after {_fmt_int(event.after_tokens)}  "
                f"net loss {_fmt_int(event.dropped_tokens)}")
            for block in event.dropped_top:
                kind_label = block.kind.replace("_", " ")
                out(paint(f"    ✝ {_fmt_int(block.tokens).rjust(8)}  {kind_label:<12} "
                          f"{block.name}  └ {block.preview}", _DIM))
        out("")

    # --- warnings ------------------------------------------------------------------
    if report.warnings:
        out(paint(f"warnings ({len(report.warnings)})", _DIM))
        for warning in report.warnings[:6]:
            out(paint(f"  · {warning}", _DIM))
        if len(report.warnings) > 6:
            out(paint(f"  · … and {len(report.warnings) - 6} more", _DIM))
        out("")

    return "\n".join(lines)
