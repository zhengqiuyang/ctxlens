"""Command line interface.

Exit codes (the whole contract, kept boring):

- ``0`` — success, including a scan that found nothing alarming
- ``1`` — nothing to scan (no session found, unreadable path, unknown agent)
- ``2`` — usage error (argparse's own)
- ``3`` — budget breach: ``--max-tokens`` given and the live context exceeds it

``3`` is the CI gate: point your pipeline at a session file, fail the job the
moment an agent's context runs away.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from . import __version__
from .adapters import AGENT_NAMES, parse_session
from .analyze import analyze
from .demo import build_demo_session
from .discover import discover
from .models import SessionReport
from .render import render_svg, render_terminal

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_BUDGET = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctxlens",
        description="X-ray for your coding agent's context window — "
        "what ate your tokens? Deterministic, zero LLM, local-first.",
    )
    parser.add_argument("--version", action="version", version=f"ctxlens {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_sessions = sub.add_parser(
        "sessions", help="list session logs found on this machine (newest first)"
    )
    p_sessions.add_argument("--agent", default="auto",
                            help=f"filter by agent: {', '.join(('auto',) + AGENT_NAMES)}")
    p_sessions.add_argument("--limit", type=int, default=15)

    p_scan = sub.add_parser(
        "scan", help="X-ray one session file (default: the most recent one)"
    )
    p_scan.add_argument("path", nargs="?", default=None,
                        help="path to a session .jsonl file, or - for stdin")
    p_scan.add_argument("--agent", default="auto",
                        help=f"adapter to use: {', '.join(('auto',) + AGENT_NAMES)}")
    p_scan.add_argument("--top", type=int, default=10,
                        help="how many offenders to show (default 10)")
    p_scan.add_argument("--format", choices=("terminal", "svg", "json"),
                        default="terminal")
    p_scan.add_argument("--out", type=Path, default=None,
                        help="write the report to this file instead of stdout")
    p_scan.add_argument("--max-tokens", type=int, default=None,
                        help="exit 3 if the live context exceeds this — the CI gate")
    p_scan.add_argument("--no-color", action="store_true")
    p_scan.add_argument("--demo", action="store_true",
                        help="X-ray the built-in fictional session instead of a real one")
    return parser


def _parse_or_none(source: Path, agent: str, warnings: List[str]):
    """Parse with a friendly message instead of a traceback on bad agents."""
    try:
        return parse_session(source, agent, warnings)
    except ValueError as exc:
        print(f"ctxlens: {exc}", file=sys.stderr)
        return None


def _scan_source(args: argparse.Namespace) -> tuple:
    """Resolve what to scan into (parsed_session, source_label, warnings).

    Returns (None, "", warnings) on any failure — the caller prints the
    human-facing message and turns it into exit code 1.
    """
    warnings: List[str] = []
    if args.demo:
        return build_demo_session(), "demo session (fictional)", warnings
    path = args.path
    if path is None:
        ref = discover(args.agent if args.agent != "generic" else None)
        if not ref:
            return None, "", warnings
        path = str(ref[0].path)
    if path == "-":
        text = sys.stdin.read()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        try:
            parsed = _parse_or_none(tmp_path, args.agent, warnings)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if parsed is None:
            return None, "", warnings
        return parsed, "stdin", warnings
    source = Path(path)
    if not source.is_file():
        print(f"ctxlens: no such file: {source}", file=sys.stderr)
        return None, "", warnings
    parsed = _parse_or_none(source, args.agent, warnings)
    if parsed is None:
        return None, "", warnings
    return parsed, str(source), warnings


def _emit(report: SessionReport, args: argparse.Namespace) -> str:
    if args.format == "json":
        text = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    elif args.format == "svg":
        text = render_svg(report, top=min(args.top, 10))
    else:
        text = render_terminal(report, top=args.top, color=not args.no_color)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"ctxlens: wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    return text


def _cmd_sessions(args: argparse.Namespace) -> int:
    refs = discover(args.agent if args.agent != "generic" else None)
    if not refs:
        print("ctxlens: no session logs found.", file=sys.stderr)
        print("  looked in ~/.claude/projects and ~/.codex/sessions "
              "(override with CTXLENS_HOME)", file=sys.stderr)
        print("  try `ctxlens scan --demo` to see what a report looks like",
              file=sys.stderr)
        return _EXIT_ERROR
    for ref in refs[: max(args.limit, 1)]:
        print(ref.label())
    return _EXIT_OK


def _cmd_scan(args: argparse.Namespace) -> int:
    parsed, source, warnings = _scan_source(args)
    if parsed is None:
        print("ctxlens: no session logs found to scan.", file=sys.stderr)
        print("  pass a file: ctxlens scan path/to/session.jsonl", file=sys.stderr)
        print("  or try the built-in demo: ctxlens scan --demo", file=sys.stderr)
        return _EXIT_ERROR
    if not parsed.blocks:
        print(f"ctxlens: no context blocks found in {source}", file=sys.stderr)
        if warnings:
            print(f"  ({len(warnings)} line(s) were unreadable)", file=sys.stderr)
        return _EXIT_ERROR
    report = analyze(parsed, source, warnings)
    _emit(report, args)
    if args.max_tokens is not None and report.latest_context_tokens > args.max_tokens:
        print(
            f"ctxlens: budget breach — live context "
            f"{report.latest_context_tokens:,} exceeds --max-tokens {args.max_tokens:,}",
            file=sys.stderr,
        )
        return _EXIT_BUDGET
    return _EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else None)

    if args.command == "sessions":
        return _cmd_sessions(args)
    if args.command == "scan":
        return _cmd_scan(args)
    # No subcommand: behave like `scan` with defaults.
    args.path = None
    args.agent = "auto"
    args.top = 10
    args.format = "terminal"
    args.out = None
    args.max_tokens = None
    args.no_color = False
    args.demo = False
    return _cmd_scan(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
