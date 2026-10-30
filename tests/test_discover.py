"""Discovery: sandboxed homes, filtering, ordering — never the real home."""

import time
from pathlib import Path

from ctxlens.discover import discover, latest

FIXTURES = Path(__file__).parent / "fixtures"


def _make_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    claude_dir = home / ".claude" / "projects" / "repo"
    codex_dir = home / ".codex" / "sessions" / "2026" / "10" / "30"
    claude_dir.mkdir(parents=True)
    codex_dir.mkdir(parents=True)
    claude_file = claude_dir / "abc.jsonl"
    codex_file = codex_dir / "rollout-1.jsonl"
    claude_file.write_text(
        (FIXTURES / "claude_session.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    codex_file.write_text(
        (FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # deterministic mtimes: codex newer
    old = time.time() - 3600
    import os

    os.utime(claude_file, (old, old))
    return home


def test_discover_finds_both_agents_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXLENS_HOME", str(_make_home(tmp_path)))
    refs = discover()
    assert [r.agent for r in refs] == ["codex", "claude"]
    assert refs[0].path.name == "rollout-1.jsonl"


def test_discover_filters_by_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXLENS_HOME", str(_make_home(tmp_path)))
    refs = discover("claude")
    assert len(refs) == 1
    assert refs[0].agent == "claude"


def test_discover_empty_home_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXLENS_HOME", str(tmp_path / "void"))
    assert discover() == []
    assert latest() is None


def test_latest_returns_newest(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXLENS_HOME", str(_make_home(tmp_path)))
    ref = latest()
    assert ref is not None and ref.agent == "codex"


def test_discover_ignores_empty_files(tmp_path, monkeypatch):
    home = _make_home(tmp_path)
    (home / ".claude" / "projects" / "repo" / "empty.jsonl").write_text(
        "", encoding="utf-8"
    )
    monkeypatch.setenv("CTXLENS_HOME", str(home))
    refs = discover("claude")
    assert [r.path.name for r in refs] == ["abc.jsonl"]


def test_label_contains_name_and_size(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXLENS_HOME", str(_make_home(tmp_path)))
    ref = latest()
    label = ref.label()
    assert ref.path.name in label
    assert ref.agent in label
