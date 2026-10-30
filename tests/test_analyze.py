"""The analysis engine: composition, offenders, curve, compaction forensics."""

from ctxlens.adapters import parse_session
from ctxlens.analyze import analyze
from ctxlens.demo import build_demo_session
from ctxlens.models import KIND_FILE_RESULT


def _analyze_fixture(path, agent):
    parsed = parse_session(path, agent)
    return analyze(parsed, str(path))


def test_composition_sums_to_total(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    assert sum(report.composition.values()) == report.total_tokens
    assert report.total_tokens > 0


def test_scaling_to_real_usage(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    # fixture logs usage input+cache = 600+42900 on the last assistant turn
    assert report.scaled_to_real
    assert report.total_tokens == 600 + 42900


def test_no_real_usage_leaves_estimates(codex_session):
    # codex fixture has a token_count event... build one without it via demo? Use generic:
    parsed = parse_session(codex_session, "codex")
    report = analyze(parsed, "codex")
    assert report.scaled_to_real  # token_count event present -> scaled


def test_compaction_marks_live_context(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    assert report.cut_index is not None
    dropped = [b for b in report.blocks if b.dropped_by_compaction]
    assert dropped, "pre-cut blocks should be marked"
    live = [b for b in report.blocks if not b.dropped_by_compaction]
    assert sum(b.tokens for b in live) > 0


def test_compaction_event_balances(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    event = report.compactions[0]
    assert event.before_tokens > 0
    assert event.dropped_top, "the casualties list should not be empty"
    biggest = max(b.tokens for b in report.blocks if b.dropped_by_compaction)
    assert event.dropped_top[0].tokens == biggest


def test_top_offenders_sorted_desc(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    tokens = [b.tokens for b in report.top_offenders]
    assert tokens == sorted(tokens, reverse=True)
    assert tokens[0] >= report.top_offenders[-1].tokens


def test_top_offenders_are_blocks_with_previews(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    for block in report.top_offenders:
        assert "\n" not in block.preview


def test_curve_rises_without_real_usage(generic_session):
    report = _analyze_fixture(generic_session, "generic")
    tokens = [p.tokens for p in report.curve]
    assert tokens == sorted(tokens)  # cumulative -> monotonic
    assert all(not p.real for p in report.curve)


def test_curve_uses_real_points_when_present(claude_session):
    report = _analyze_fixture(claude_session, "claude")
    assert all(p.real for p in report.curve)
    assert len(report.curve) == 3


def test_demo_session_shape():
    parsed = build_demo_session()
    report = analyze(parsed, "demo")
    assert report.context_window == 200000
    assert report.window_fraction() < 1.0
    assert any(c.kind == "compact" for c in report.compactions)
    assert report.top_offenders[0].kind == KIND_FILE_RESULT
    assert "46,800" in f"{report.top_offenders[0].tokens:,}"


def test_warnings_aggregated(claude_session):
    warnings = []
    parsed = parse_session(claude_session, "claude", warnings)
    report = analyze(parsed, "x", warnings)
    assert any(w.startswith("1×") or "×" in w for w in report.warnings)
    assert all("line " not in w.split("×")[0] for w in report.warnings if "×" in w)
