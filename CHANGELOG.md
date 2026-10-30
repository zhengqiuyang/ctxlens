# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- OpenCode adapter
- `ctxlens watch` — live window gauge during a session
- Cross-session drift report
- Flamegraph view of nested tool results

## [0.1.0] — 2026-10-31

### Added

- Deterministic token estimator: ASCII ≈ 4 chars/token, CJK ≈ 1 char/token;
  same input, same output, forever.
- Session adapters: Claude Code (real usage points, compaction detection via
  `isCompactSummary` and continuation prose), Codex CLI (`session_meta`
  `context_window`, `token_count` events, call-id → tool attribution), and a
  generic JSONL fallback with role/type heuristics.
- Analysis engine, all pure functions: six-bucket composition of the live
  context, top-offenders ranking with previews, compaction forensics
  (before/after, net loss, five largest casualties), bloat curve from real
  usage points or a deterministic cumulative estimate.
- Renderers: terminal ANSI (readable with color stripped), byte-identical
  dark-theme SVG, JSON.
- Discovery of session logs under `~/.claude/projects` and
  `~/.codex/sessions`, newest first; `CTXLENS_HOME` redirects the root.
- CLI: `scan` (file, stdin, demo, auto-discovery) and `sessions`;
  `--agent`, `--format`, `--out`, `--top`, `--max-tokens`, `--no-color`.
- Exit-code contract: 0 ok · 1 nothing to scan · 2 usage · 3 budget breach.
- Built-in fictional demo session (`scan --demo`) sized like a real 2 AM
  bug hunt, including a compaction cut.
- Warning aggregation: a thousand unreadable lines become one line with a count.
- CI: the test matrix on Windows/macOS/Linux × Python 3.9–3.13, plus a ruff
  lint job. 56 tests.

### Design invariants

- Zero LLM, zero network, zero telemetry — the session file is the only input.
- Zero runtime dependencies; `pytest` and `ruff` are dev-only.
- Tolerant parsing: an unknown line is data about the file, not an error.
- Determinism: no timestamps, no randomness, no locale in any rendered output.
