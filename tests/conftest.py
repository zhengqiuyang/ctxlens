"""Shared fixtures: paths to the synthetic session files."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def claude_session() -> Path:
    return FIXTURES / "claude_session.jsonl"


@pytest.fixture
def codex_session() -> Path:
    return FIXTURES / "codex_session.jsonl"


@pytest.fixture
def generic_session() -> Path:
    return FIXTURES / "generic_session.jsonl"
