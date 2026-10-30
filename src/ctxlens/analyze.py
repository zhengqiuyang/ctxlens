"""The analysis engine: composition, offenders, curve, compaction forensics.

Pure functions over a ParsedSession — no I/O, no clocks, no randomness. Given
the same parsed session, every number below is identical across machines and
runs. That is what makes reports diffable and CI-gateable.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List

from .models import (
    BUCKET_ORDER,
    BUCKETS,
    ParsedSession,
    SessionReport,
    UsagePoint,
)

_KIND_TO_BUCKET: Dict[str, str] = {
    kind: bucket
    for bucket, kinds in BUCKETS.items()
    for kind in kinds
}

#: The bloat curve is a shape, not a table — this many points is plenty.
MAX_CURVE_POINTS = 120

_WARNING_TAIL = re.compile(r"^line \d+: (.+)$")

# Sizes below this are noise for the "top offenders" list; a 12-token tool
# call is not a story worth telling.
MIN_OFFENDER_TOKENS = 64


def _aggregate_warnings(warnings: List[str]) -> List[str]:
    """'line 4: not valid JSON' × 900 becomes one line with a count."""
    if not warnings:
        return []
    counts: Counter = Counter()
    other: List[str] = []
    for warning in warnings:
        match = _WARNING_TAIL.match(warning)
        if match:
            counts[match.group(1)] += 1
        else:
            other.append(warning)
    aggregated = [f"{count}× {reason}" for reason, count in counts.most_common()]
    return other + aggregated


def _composition(blocks: List) -> Dict[str, int]:
    buckets = {bucket: 0 for bucket in BUCKET_ORDER}
    for block in blocks:
        buckets[_KIND_TO_BUCKET.get(block.kind, "other")] += block.tokens
    return buckets


def _scale_to_real(composition: Dict[str, int], estimated_total: int,
                   real_total: int) -> Dict[str, int]:
    """Rescale estimated bucket sizes so they sum to a real usage number.

    The estimator knows the *shape* of the context (which block is big), and
    the agent's own usage line knows the *size*. Scaling one by the other is
    the most honest number we can produce — each bucket keeps its share, the
    total matches reality.
    """
    if estimated_total <= 0 or real_total <= 0:
        return composition
    factor = real_total / estimated_total
    scaled = {bucket: int(round(tokens * factor)) for bucket, tokens in composition.items()}
    # rounding drift lands on the biggest bucket; keep the sum exact
    drift = real_total - sum(scaled.values())
    if drift and composition:
        biggest = max(composition, key=lambda b: composition[b])
        scaled[biggest] += drift
    return scaled


def _build_curve(parsed: ParsedSession, blocks: List) -> List[UsagePoint]:
    """Real usage points when the agent logged them; else a deterministic
    cumulative estimate, strided down to a drawable number of points."""
    if parsed.usage_points:
        return list(parsed.usage_points)
    if not blocks:
        return []
    cumulative = []
    running = 0
    for block in blocks:
        running += block.tokens
        cumulative.append(UsagePoint(tokens=running, real=False,
                                     label=f"block {block.index}"))
    if len(cumulative) <= MAX_CURVE_POINTS:
        return cumulative
    step = math.ceil(len(cumulative) / MAX_CURVE_POINTS)
    strided = cumulative[::step]
    if strided[-1] is not cumulative[-1]:
        strided.append(cumulative[-1])
    return strided


def _compaction_events(parsed: ParsedSession, blocks: List) -> List:
    from .models import CompactionEvent

    events = []
    for mark_index, kind in parsed.compaction_marks:
        if mark_index >= len(blocks):
            continue
        before_blocks = blocks[:mark_index]
        after_blocks = blocks[mark_index:]
        before = sum(b.tokens for b in before_blocks)
        after = sum(b.tokens for b in after_blocks)
        dropped_top = sorted(before_blocks, key=lambda b: b.tokens, reverse=True)[:5]
        for block in before_blocks:
            block.dropped_by_compaction = True
        events.append(
            CompactionEvent(
                index=mark_index,
                kind=kind,
                before_tokens=before,
                after_tokens=after,
                dropped_tokens=max(0, before - (after - blocks[mark_index].tokens)),
                dropped_top=dropped_top,
            )
        )
    return events


def analyze(
    parsed: ParsedSession, source: str, warnings: List[str] | None = None
) -> SessionReport:
    """Full analysis of one parsed session. See SessionReport for the shape."""
    blocks = parsed.blocks
    file_total = sum(b.tokens for b in blocks)

    # Live context = what survives the most recent compaction cut. The window
    # cares about now, not the archaeology of the whole file.
    if parsed.compaction_marks:
        cut = min(max(m[0] for m in parsed.compaction_marks), len(blocks))
        live_blocks = blocks[cut:]
    else:
        cut = 0
        live_blocks = blocks

    composition = _composition(live_blocks)
    live_total = sum(composition.values())
    scaled = False

    # Real usage ground truth: the agent's own last prompt-size line is the
    # best measurement of the live context; the estimator supplies the shape.
    real_points = [p for p in parsed.usage_points if p.real]
    if real_points and live_total > 0:
        target = real_points[-1].tokens
        composition = _scale_to_real(composition, live_total, target)
        live_total = sum(composition.values())
        scaled = True

    report = SessionReport(
        source=source,
        agent=parsed.agent,
        session_id=parsed.session_id,
        model=parsed.model,
        context_window=parsed.context_window,
        blocks=blocks,
        composition=composition,
        total_tokens=live_total,
        scaled_to_real=scaled,
        file_total_tokens=file_total,
        cut_index=cut if parsed.compaction_marks else None,
        top_offenders=sorted(
            (b for b in blocks if b.tokens >= MIN_OFFENDER_TOKENS),
            key=lambda b: b.tokens,
            reverse=True,
        )[:10],
        curve=_build_curve(parsed, blocks),
        compactions=_compaction_events(parsed, blocks),
        warnings=_aggregate_warnings(list(warnings or [])),
        line_count=parsed.line_count,
    )
    return report
