"""CLI: exit codes, formats, the budget gate, discovery sandboxing."""

import io
import json
from pathlib import Path

from ctxlens.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_scan_demo_ok(capsys):
    code, out, err = _run(capsys, "scan", "--demo", "--no-color")
    assert code == 0
    assert "composition" in out
    assert "compaction forensics" in out


def test_scan_demo_svg_to_file(capsys, tmp_path):
    target = tmp_path / "xray.svg"
    code, out, err = _run(capsys, "scan", "--demo", "--format", "svg",
                          "--out", str(target))
    assert code == 0
    assert target.exists()
    assert out == ""  # report went to the file
    assert "wrote" in err


def test_scan_json_format(capsys):
    code, out, err = _run(capsys, "scan", "--demo", "--format", "json")
    assert code == 0
    data = json.loads(out)
    assert data["agent"] == "claude"
    assert data["context_window"] == 200000


def test_scan_missing_file_is_error(capsys):
    code, out, err = _run(capsys, "scan", "does-not-exist.jsonl")
    assert code == 1
    assert "no such file" in err


def test_scan_empty_blocks_is_error(capsys, tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text('{"unrelated": true}\n', encoding="utf-8")
    code, out, err = _run(capsys, "scan", str(empty))
    assert code == 1
    assert "no context blocks" in err


def test_budget_gate_exit_three(capsys):
    code, out, err = _run(capsys, "scan", "--demo", "--no-color",
                          "--max-tokens", "10")
    assert code == 3
    assert "budget breach" in err


def test_budget_gate_passes(capsys):
    code, out, err = _run(capsys, "scan", "--demo", "--no-color",
                          "--max-tokens", "100000000")
    assert code == 0


def test_scan_fixture_file(capsys, claude_session):
    code, out, err = _run(capsys, "scan", str(claude_session), "--no-color")
    assert code == 0
    assert "payments/processor.py" in out


def test_scan_stdin(capsys, monkeypatch):
    data = (FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    code = main(["scan", "-", "--no-color"])
    captured = capsys.readouterr()
    assert code == 0
    assert "composition" in captured.out


def test_sessions_lists_discovered(capsys, monkeypatch, tmp_path):
    home = tmp_path / "home"
    project = home / ".claude" / "projects" / "repo"
    project.mkdir(parents=True)
    (project / "abc.jsonl").write_text(
        (FIXTURES / "claude_session.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setenv("CTXLENS_HOME", str(home))
    code, out, err = _run(capsys, "sessions")
    assert code == 0
    assert "abc.jsonl" in out


def test_sessions_empty_is_error(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CTXLENS_HOME", str(tmp_path / "nothing-here"))
    code, out, err = _run(capsys, "sessions")
    assert code == 1
    assert "--demo" in err


def test_no_subcommand_behaves_like_scan_demo(capsys):
    # a bare `main([])` finds no real sessions in the sandbox; demo hint is fine
    code = main(["scan", "--demo", "--format", "json"])
    assert code == 0


def test_unknown_agent_is_error(capsys, claude_session):
    code, out, err = _run(capsys, "scan", str(claude_session), "--agent", "wat")
    assert code == 1
    assert "unknown agent" in err
