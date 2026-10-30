"""SVG renderer: the session X-ray as a shareable dark-theme chart.

Output is fully deterministic — no timestamps, no random ids — so the same
session always renders byte-identical SVG. That makes the files diffable and
the tests trivial.
"""

from __future__ import annotations

from xml.sax.saxutils import escape
from typing import List, Tuple

from .. import __version__
from ..models import BUCKET_ORDER, SessionReport

# X-ray theme: dark plate, luminous tissue.
_BG = "#0b0e14"
_PANEL = "#11151f"
_GRID = "#1c2230"
_TEXT = "#c7d0e0"
_MUTED = "#6b7689"

_BUCKET_COLORS = {
    "system": "#b267e6",
    "user": "#4fc1ff",
    "assistant": "#5b8def",
    "tool_calls": "#e8c468",
    "tool_results": "#ff6b6b",
    "other": "#7d8aa0",
}

_WIDTH = 960
_BAR_Y = 96
_BAR_H = 34
_CURVE_TOP = 236
_CURVE_H = 210
_TABLE_TOP = 500
_ROW_H = 30
_AXIS_PAD = 72  # right margin reserved for curve axis labels


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _short(text: str, limit: int = 44) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _legend_parts(report: SessionReport) -> List[Tuple[str, int, float]]:
    total = max(1, report.total_tokens)
    parts = []
    for bucket in BUCKET_ORDER:
        tokens = report.composition.get(bucket, 0)
        if tokens > 0:
            parts.append((bucket, tokens, tokens / total))
    return parts


def render_svg(report: SessionReport, top: int = 8) -> str:
    parts: List[str] = []
    out = parts.append

    offenders = report.top_offenders[:top]
    height = _TABLE_TOP + 24 + len(offenders) * _ROW_H + 46
    out(f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" '
        f'viewBox="0 0 {_WIDTH} {height}" font-family="ui-monospace,\'Cascadia Code\','
        f'Consolas,Menlo,monospace" font-size="13">')
    out(f'<rect width="{_WIDTH}" height="720" fill="{_BG}"/>')

    # --- header -----------------------------------------------------------
    out(f'<text x="32" y="42" fill="{_TEXT}" font-size="20" font-weight="bold">'
        f'ctxlens — session X-ray</text>')
    subtitle = f"agent: {escape(report.agent)}"
    if report.model:
        subtitle += f"   model: {escape(report.model)}"
    sid = _short(report.session_id, 18)
    if sid:
        subtitle += f"   session: {escape(sid)}"
    out(f'<text x="32" y="64" fill="{_MUTED}">{escape(subtitle)}</text>')

    # --- composition bar -----------------------------------------------------
    inner_x, inner_w = 32.0, _WIDTH - 64.0
    legend = _legend_parts(report)
    cursor = inner_x
    for bucket, tokens, share in legend:
        seg_w = share * inner_w
        color = _BUCKET_COLORS[bucket]
        out(f'<rect x="{cursor:.1f}" y="{_BAR_Y}" width="{max(seg_w, 0):.1f}" '
            f'height="{_BAR_H}" fill="{color}"/>')
        if seg_w > 54:
            label = f"{escape(bucket.replace('_', ' '))} {_share_text(share)}"
            out(f'<text x="{cursor + seg_w / 2:.1f}" y="{_BAR_Y + _BAR_H / 2 + 4}" '
                f'fill="{_BG}" font-size="11" text-anchor="middle">{label}</text>')
        cursor += seg_w
    out(f'<rect x="{inner_x}" y="{_BAR_Y}" width="{inner_w:.1f}" height="{_BAR_H}" '
        f'fill="none" stroke="{_GRID}"/>')
    out(f'<text x="{inner_x}" y="{_BAR_Y - 8}" fill="{_MUTED}">live context '
        f'{_fmt_int(report.total_tokens)} tokens'
        + (f" of {_fmt_int(report.context_window)} window"
           if report.context_window else "")
        + ("  · buckets scaled to real usage" if report.scaled_to_real else "")
        + "</text>")

    # legend swatches, two rows max
    lx, ly = inner_x, _BAR_Y + _BAR_H + 20
    for i, (bucket, tokens, _share) in enumerate(legend):
        col, row = i % 3, i // 3
        x = lx + col * 300
        y = ly + row * 18
        out(f'<rect x="{x}" y="{y - 9}" width="10" height="10" '
            f'fill="{_BUCKET_COLORS[bucket]}"/>')
        out(f'<text x="{x + 16}" y="{y}" fill="{_TEXT}" font-size="11">'
            f'{escape(bucket.replace("_", " "))}  {_fmt_int(tokens)}</text>')

    # --- bloat curve ------------------------------------------------------------
    curve = [p.tokens for p in report.curve]
    if curve:
        out(f'<text x="{inner_x}" y="{_CURVE_TOP - 24}" fill="{_TEXT}" '
            f'font-weight="bold">bloat curve — context size across the session</text>')
        plot_x, plot_w = inner_x, inner_w - _AXIS_PAD
        plot_y, plot_h = _CURVE_TOP, _CURVE_H
        lo, hi = min(curve), max(curve)
        span = max(1, hi - lo)

        def px(i: int) -> float:
            step = plot_w / max(1, len(curve) - 1)
            return plot_x + i * step

        def py(v: int) -> float:
            return plot_y + plot_h - (v - lo) / span * plot_h

        # grid: 4 horizontal lines
        for g in range(5):
            gy = plot_y + plot_h * g / 4
            gv = hi - span * g / 4
            out(f'<line x1="{plot_x:.0f}" y1="{gy:.0f}" x2="{plot_x + plot_w:.0f}" '
                f'y2="{gy:.0f}" stroke="{_GRID}"/>')
            out(f'<text x="{plot_x + plot_w + 6:.0f}" y="{gy + 4:.0f}" fill="{_MUTED}" '
                f'font-size="10">{_fmt_int(int(gv))}</text>')

        # compaction cuts as dashed verticals
        for event in report.compactions:
            cut_i = min(event.index, len(curve) - 1)
            cx = px(cut_i)
            out(f'<line x1="{cx:.1f}" y1="{plot_y}" x2="{cx:.1f}" y2="{plot_y + plot_h}" '
                f'stroke="#ff6b6b" stroke-dasharray="4 4" opacity="0.7"/>')
            out(f'<path d="M {cx:.1f} {plot_y + plot_h + 6} l -5 8 l 10 0 z" '
                f'fill="#ff6b6b" opacity="0.8"/>')

        points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(curve))
        out(f'<polyline points="{points}" fill="none" stroke="#4fc1ff" stroke-width="2"/>')

    # --- top offenders table ---------------------------------------------------
    out(f'<text x="{inner_x}" y="{_TABLE_TOP}" fill="{_TEXT}" font-weight="bold">'
        f'top offenders — the blocks that ate the window</text>')
    if offenders:
        max_tokens = max(b.tokens for b in offenders)
        for i, block in enumerate(offenders):
            y = _TABLE_TOP + 24 + i * _ROW_H
            color = _BUCKET_COLORS.get(
                "tool_results" if block.kind in ("tool_result", "file_result") else
                "tool_calls" if block.kind == "tool_call" else
                "system" if block.kind in ("system", "summary") else
                "user" if block.kind == "user_text" else
                "assistant" if block.kind in ("assistant_text", "reasoning") else "other",
                _BUCKET_COLORS["other"],
            )
            out(f'<text x="{inner_x}" y="{y}" fill="{_MUTED}" font-size="11">{i + 1:>2}</text>')
            out(f'<rect x="{inner_x + 28}" y="{y - 10}" width="{block.tokens / max_tokens * 300:.1f}" '
                f'height="13" fill="{color}" opacity="0.85"/>')
            label = f"{block.kind.replace('_', ' ')} · {escape(_short(block.name or 'tool', 26))}"
            out(f'<text x="{inner_x + 340}" y="{y}" fill="{_TEXT}" font-size="11">{label}</text>')
            out(f'<text x="{_WIDTH - 32}" y="{y}" fill="{_MUTED}" font-size="11" '
                f'text-anchor="end">{_fmt_int(block.tokens)}</text>')
            if block.preview:
                out(f'<text x="{inner_x + 340}" y="{y + 12}" fill="{_MUTED}" font-size="10">'
                    f'{escape(_short(block.preview, 80))}</text>')

    # --- footer -----------------------------------------------------------------
    out(f'<text x="{inner_x}" y="{height - 18}" fill="{_MUTED}" font-size="11">'
        f'ctxlens v{__version__} — deterministic estimates, zero LLM, zero network'
        + ("  · sizes scaled to the agent\'s own usage report" if report.scaled_to_real else "")
        + "</text>")

    out("</svg>")
    return "\n".join(parts)


def _share_text(share: float) -> str:
    return f"{share * 100:.1f}%"
