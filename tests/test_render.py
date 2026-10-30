"""Renderers: readable without color, deterministic SVG, loadable JSON."""

import json
import xml.etree.ElementTree as ET

from ctxlens.adapters import parse_session
from ctxlens.analyze import analyze
from ctxlens.demo import build_demo_session
from ctxlens.render import render_svg, render_terminal


def _report(path, agent):
    return analyze(parse_session(path, agent), str(path))


def _demo_report():
    return analyze(build_demo_session(), "demo")


def test_terminal_has_all_sections(claude_session):
    text = render_terminal(_report(claude_session, "claude"), color=False)
    assert "composition" in text
    assert "top offenders" in text
    assert "bloat curve" in text
    assert "compaction forensics" in text


def test_terminal_single_line_previews(claude_session):
    text = render_terminal(_report(claude_session, "claude"), color=False)
    for line in text.splitlines():
        assert line.count("\n") == 0


def test_terminal_no_color_codes_when_disabled(claude_session):
    text = render_terminal(_report(claude_session, "claude"), color=False)
    assert "\x1b[" not in text


def test_terminal_budget_alarm(demo=None):
    report = _demo_report()
    text = render_terminal(report, color=False)
    # demo sits at ~25% post-compact: no alarm line
    assert "80%+" not in text


def test_svg_is_well_formed_xml(claude_session):
    text = render_svg(_report(claude_session, "claude"))
    root = ET.fromstring(text)
    assert root.tag.endswith("svg")


def test_svg_deterministic(claude_session):
    a = render_svg(_report(claude_session, "claude"))
    b = render_svg(_report(claude_session, "claude"))
    assert a == b


def test_svg_draws_curve_and_cuts():
    text = render_svg(_demo_report())
    assert "<polyline" in text
    assert 'stroke-dasharray="4 4"' in text  # compaction cut markers
    assert "46,800" in text  # the demo's biggest offender


def test_svg_escapes_hostile_text():
    from ctxlens.models import Block, ParsedSession, KIND_USER

    parsed = ParsedSession(agent="claude", blocks=[
        Block(kind=KIND_USER, tokens=100, index=0, name="user",
              preview='<script>alert("x")</script> & <b>bold</b>'),
    ])
    text = render_svg(analyze(parsed, "x"))
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_json_report_round_trips(claude_session):
    report = _report(claude_session, "claude")
    data = json.loads(json.dumps(report.to_dict()))
    assert data["agent"] == "claude"
    assert data["total_tokens"] == report.total_tokens
    assert data["scaled_to_real"] is True
    assert isinstance(data["top_offenders"], list)
