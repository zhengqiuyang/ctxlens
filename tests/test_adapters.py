"""Adapters: parse synthetic sessions built from each tool's real dialect."""

from ctxlens.adapters import detect_agent, parse_session
from ctxlens.models import (
    KIND_ASSISTANT,
    KIND_FILE_RESULT,
    KIND_REASONING,
    KIND_SYSTEM,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
)


def test_claude_kinds_in_order(claude_session):
    parsed = parse_session(claude_session, "claude")
    kinds = [b.kind for b in parsed.blocks]
    # the compact summary re-enters the session as a user-role message
    assert kinds == [
        KIND_USER,
        KIND_TOOL_CALL,
        KIND_FILE_RESULT,
        KIND_ASSISTANT,
        KIND_REASONING,
        KIND_USER,
        KIND_USER,
    ]
    assert parsed.session_id == "claude-test-0001"


def test_claude_tool_name_and_file_attribution(claude_session):
    parsed = parse_session(claude_session, "claude")
    file_block = next(b for b in parsed.blocks if b.kind == KIND_FILE_RESULT)
    assert file_block.name == "payments/processor.py"


def test_claude_real_usage_points(claude_session):
    parsed = parse_session(claude_session, "claude")
    real = [p for p in parsed.usage_points if p.real]
    assert len(real) == 3
    assert real[0].tokens == 412 + 18100  # input + cache_creation


def test_claude_compaction_mark(claude_session):
    parsed = parse_session(claude_session, "claude")
    assert parsed.compaction_marks, "compact summary should be marked"
    assert parsed.compaction_marks[0][1] == "compact"


def test_claude_tolerates_bad_lines(claude_session):
    warnings = []
    parsed = parse_session(claude_session, "claude", warnings)
    assert parsed.line_count == 7  # 8 lines, one is not JSON and is skipped
    assert any("not valid JSON" in w for w in warnings)


def test_claude_unknown_content_item_warns(claude_session):
    warnings = []
    parse_session(claude_session, "claude", warnings)
    assert any("mystery_block" in w for w in warnings)


def test_codex_session_meta(codex_session):
    parsed = parse_session(codex_session, "codex")
    assert parsed.context_window == 200000
    assert parsed.model == "gpt-6.1-sol"
    assert parsed.session_id == "codex-test-0002"
    assert parsed.cwd == "/repo"


def test_codex_kinds(codex_session):
    parsed = parse_session(codex_session, "codex")
    kinds = [b.kind for b in parsed.blocks]
    assert kinds == [
        KIND_SYSTEM,        # base_instructions
        KIND_SYSTEM,        # developer message
        KIND_USER,
        KIND_TOOL_CALL,
        KIND_FILE_RESULT,   # read_file output
    ]


def test_codex_output_attributed_to_tool(codex_session):
    parsed = parse_session(codex_session, "codex")
    result = next(b for b in parsed.blocks if b.kind == KIND_FILE_RESULT)
    assert result.name == "read_file"


def test_codex_token_count_event(codex_session):
    parsed = parse_session(codex_session, "codex")
    real = [p for p in parsed.usage_points if p.real]
    assert real and real[0].tokens == 18320


def test_codex_skips_unknown_types(codex_session):
    warnings = []
    parse_session(codex_session, "codex", warnings)
    assert any("world_state" in w for w in warnings)


def test_generic_maps_roles(generic_session):
    parsed = parse_session(generic_session, "generic")
    kinds = [b.kind for b in parsed.blocks]
    # the telemetry line carries no text, so the generic adapter skips it
    assert kinds == [
        KIND_SYSTEM,
        KIND_USER,
        KIND_TOOL_CALL,
        KIND_TOOL_RESULT,
        KIND_ASSISTANT,
    ]


def test_generic_skips_empty_metadata(generic_session):
    parsed = parse_session(generic_session, "generic")
    previews = [b.preview for b in parsed.blocks]
    assert all(p.strip() for p in previews)


def test_detect_agent(claude_session, codex_session, generic_session):
    assert detect_agent(claude_session) == "claude"
    assert detect_agent(codex_session) == "codex"
    assert detect_agent(generic_session) == "generic"


def test_wrong_adapter_does_not_crash(codex_session):
    warnings = []
    parsed = parse_session(codex_session, "claude", warnings)
    # a wrong dialect yields nothing useful, but never an exception
    assert parsed.blocks == []
    assert warnings, "the mismatch should at least be reported"
