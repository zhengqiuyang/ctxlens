"""A built-in fictional session for ``ctxlens --demo``.

Every byte here is invented — a believable 2 AM payment-bug hunt, sized the
way real sessions feel. Demo output is for trying the tool, generating the
README screenshot, and testing renderers against rich data without touching
anyone's real logs.
"""

from __future__ import annotations

from .models import (
    KIND_ASSISTANT,
    KIND_FILE_RESULT,
    KIND_REASONING,
    KIND_SUMMARY,
    KIND_SYSTEM,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    Block,
    ParsedSession,
    UsagePoint,
)
from .adapters.base import clean_preview


def _b(kind: str, tokens: int, name: str, preview: str, dropped: bool = False) -> Block:
    return Block(kind=kind, tokens=tokens, index=0, name=name,
                 preview=clean_preview(preview), dropped_by_compaction=dropped)


def build_demo_session() -> ParsedSession:
    blocks = [
        _b(KIND_SYSTEM, 12_400, "base_instructions",
           "You are Claude Code, Anthropic's official CLI for Claude."),
        _b(KIND_USER, 214, "user",
           "The retry logic in payments/processor.py double-charges on timeouts. Fix it tonight."),
        _b(KIND_TOOL_CALL, 486, "Read",
           '{"file_path": "payments/processor.py", "limit": 2000}'),
        _b(KIND_FILE_RESULT, 46_800, "payments/processor.py",
           "import asyncio\nfrom dataclasses import dataclass\n# ... 1,900 lines of payment plumbing ..."),
        _b(KIND_TOOL_CALL, 322, "Read", '{"file_path": "payments/retry_policy.py"}'),
        _b(KIND_FILE_RESULT, 18_200, "payments/retry_policy.py",
           "RETRY_WINDOWS = {\"default\": 3, \"webhook\": 5}  # ... policy table ..."),
        _b(KIND_ASSISTANT, 902, "assistant",
           "Found it — `charge()` fires before the idempotency key is persisted, so a timeout replays the charge."),
        _b(KIND_REASONING, 1_150, "thinking",
           "The race: key write happens after the HTTP call returns; a lost response never records the key..."),
        _b(KIND_TOOL_CALL, 258, "Edit",
           '{"file_path": "payments/processor.py", "new_string": "key = persist_idempotency(intent)"}'),
        _b(KIND_TOOL_RESULT, 96, "Edit", "The file payments/processor.py has been updated."),
        _b(KIND_TOOL_CALL, 142, "Bash", "python -m pytest tests/test_payments.py -x"),
        _b(KIND_TOOL_RESULT, 4_240, "Bash",
           "============================= test session starts ============================== ..."),
        _b(KIND_ASSISTANT, 748, "assistant",
           "One failure left: the retry window still races the webhook handler."),
        _b(KIND_TOOL_CALL, 236, "WebFetch", "https://docs.stripe.com/api/idempotent-requests"),
        _b(KIND_TOOL_RESULT, 31_500, "WebFetch",
           "Idempotency Keys — Stripe Documentation ... (full page body, navigation included) ..."),
        _b(KIND_ASSISTANT, 640, "assistant",
           "Stripe's pattern: store the key before the first attempt, replay the stored response on retries."),
        _b(KIND_TOOL_CALL, 296, "Edit",
           '{"file_path": "payments/retry_policy.py", "old_string": "RETRY_WINDOWS = ..."}'),
        _b(KIND_TOOL_RESULT, 118, "Edit", "The file payments/retry_policy.py has been updated."),
        _b(KIND_TOOL_CALL, 138, "Bash", "python -m pytest tests/test_payments.py -q"),
        _b(KIND_TOOL_RESULT, 386, "Bash", "13 passed in 4.02s"),
        # --- compaction fires here; everything above is marked, the summary re-enters
        _b(KIND_SUMMARY, 3_440, "summary",
           "This session is being continued from a previous conversation: double-charge bug in payments/processor.py..."),
        _b(KIND_USER, 96, "user", "continue"),
        _b(KIND_TOOL_CALL, 164, "Read", '{"file_path": "tests/test_payments.py"}'),
        _b(KIND_FILE_RESULT, 9_600, "tests/test_payments.py",
           "def test_charge_idempotent(): ... 412 lines of payment tests ..."),
        _b(KIND_TOOL_CALL, 152, "Bash", "python -m pytest tests/ -q"),
        _b(KIND_TOOL_RESULT, 3_120, "Bash",
           "47 passed in 11.83s ... coverage report follows ..."),
        _b(KIND_TOOL_CALL, 148, "Grep", '{"pattern": "RETRY_WINDOWS", "output_mode": "content"}'),
        _b(KIND_TOOL_RESULT, 2_240, "Grep",
           "payments/retry_policy.py:12: RETRY_WINDOWS = ... (18 matches across 6 files)"),
        _b(KIND_ASSISTANT, 1_040, "assistant",
           "Coverage is clean and the webhook race is closed. Opening a follow-up for the key-rotation TODO."),
        _b(KIND_TOOL_CALL, 156, "Bash", "python -m pytest tests/ -q --tb=short"),
        _b(KIND_TOOL_RESULT, 2_860, "Bash",
           "47 passed in 10.91s ... short tracebacks, warning summary ..."),
    ]
    for i, block in enumerate(blocks):
        block.index = i
    for block in blocks[:20]:  # everything before the summary is archaeology
        block.dropped_by_compaction = True

    parsed = ParsedSession(
        agent="claude",
        blocks=blocks,
        usage_points=[
            UsagePoint(tokens=18_212, real=True, label="turn 1"),
            UsagePoint(tokens=65_380, real=True, label="turn 2"),
            UsagePoint(tokens=112_456, real=True, label="turn 3"),
            UsagePoint(tokens=131_004, real=True, label="turn 4"),
            UsagePoint(tokens=171_522, real=True, label="turn 5"),
            UsagePoint(tokens=188_940, real=True, label="turn 6"),
            UsagePoint(tokens=193_115, real=True, label="turn 7"),
            UsagePoint(tokens=21_830, real=True, label="turn 8 (post-compact)"),
            UsagePoint(tokens=34_460, real=True, label="turn 9"),
            UsagePoint(tokens=42_118, real=True, label="turn 10"),
            UsagePoint(tokens=49_872, real=True, label="turn 11"),
        ],
        compaction_marks=[(20, "compact")],
        session_id="demo-2am-payment-hunt",
        model="claude-sonnet-4-5",
        context_window=200_000,
        line_count=len(blocks),
    )
    return parsed
