# ctxlens

**X-ray for your coding agent's context window.**

English | [简体中文](README.zh-CN.md)

> What ate your tokens? Deterministic answers · zero LLM · zero network · zero dependencies

[![CI](https://github.com/zhengqiuyang/ctxlens/actions/workflows/ci.yml/badge.svg)](https://github.com/zhengqiuyang/ctxlens/actions/workflows/ci.yml)
[![License: MIT](https://github.com/zhengqiuyang/ctxlens/blob/main/LICENSE)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)

## The cliff you never saw

It's 2 AM. Your agent has been hunting a double-charge bug for an hour and a
half, and it's been doing *beautiful* work — until it isn't.

It re-reads a file it read at minute nine. It asks you a question you already
answered. Then it apologizes, with that flat machine apology, and says the
conversation was *compacted*.

You know what happened. The context window filled up. Somewhere in there —
one `Read` that pulled a 1,900-line file, one `WebFetch` that swallowed a
documentation page whole — the window crossed its line, and the agent quietly
amputated its own memory to keep going.

What actually got dropped? *Nobody shows you that.*

Usage dashboards show you the **bill**. Your agent shows you a percentage.
Neither shows you the **anatomy**: which block ate 46k tokens, what the
compaction took away, where the curve went vertical.

ctxlens is the X-ray. It reads the session logs already on your disk and
answers three questions, deterministically, without a single LLM call:

1. **What's in my window right now** — system prompt, history, tool calls,
   tool results, by share.
2. **What were the biggest blocks** — the top offenders, ranked, with previews.
3. **What did compaction take** — before/after, net loss, the largest casualties.

![demo X-ray](docs/xray.svg)

## Quick start

```bash
uv tool install git+https://github.com/zhengqiuyang/ctxlens
# or: pip install git+https://github.com/zhengqiuyang/ctxlens
```

Look at the built-in fictional session first — no real logs touched:

```bash
ctxlens scan --demo
```

Then X-ray your own:

```bash
ctxlens                       # latest session, any agent
ctxlens sessions              # what logs exist on this machine
ctxlens scan ~/.codex/sessions/2026/10/28/rollout-....jsonl --format svg --out xray.svg
ctxlens scan --agent claude --top 15
```

## What it sees

**Composition.** The live context — what survives the most recent compaction —
broken into six buckets: system, user, assistant, tool calls, tool results,
other. When the agent logged its own usage numbers, ctxlens scales the bucket
shape to match that real total and says so.

**Top offenders.** The largest blocks in the session, ranked by estimated
size: a 46,800-token file read, a 31,500-token web page, the test-suite
output that kept growing. Each with a one-line preview.

**Compaction forensics.** Every cut gets a before/after balance: context size
on each side, the net loss, and the five biggest blocks that went in before
and didn't come out.

**Bloat curve.** Context size across the whole session — real usage points
when the agent logs them, deterministic estimates otherwise. Compaction cuts
drawn as cliffs. The shape tells the story at a glance.

## The gate

Reports are nice. Gates get merged. `--max-tokens` turns ctxlens into a
two-second CI check:

```bash
ctxlens scan "$SESSION_FILE" --max-tokens 150000
echo $?   # 0 under budget · 3 over budget
```

Exit codes: `0` success · `1` nothing to scan · `2` usage error ·
`3` budget breach.

## Honesty section

ctxlens never calls an LLM, never touches the network, and never pretends to
be a tokenizer.

- **Per-block sizes are estimates.** A documented heuristic (ASCII ≈ 4
  chars/token, CJK ≈ 1 char/token), typically within ~25% of real tokenizers.
  The *ranking* — which block is biggest — is robust; the exact number is a
  lantern, not a micrometer.
- **When real numbers exist, they win.** Agents that log usage (Claude Code
  does; Codex on some builds) feed ctxlens the actual prompt size, and bucket
  estimates get scaled to it — flagged as `scaled to real usage`.
- **Same input, same output, forever.** No timestamps, no randomness, no
  locale. Reports are diffable; SVG renders are byte-identical.

## Design principles

1. **Zero LLM in the analysis path.** The session file is the only input.
2. **Zero dependencies.** Pure standard library, Python 3.9+. `pytest` for dev only.
3. **Local-first.** Nothing leaves your machine because nothing is ever sent anywhere.
4. **Tolerant adapters.** Agent log formats drift every release; unknown lines
   are counted and skipped, never fatal.
5. **Determinism is a feature.** A report that shifts between runs cannot be
   baselined, diffed, or gated.

## Adapters

| Agent | Location | Status |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` | ✅ incl. real usage + compaction detection |
| Codex CLI | `~/.codex/sessions/**/*.jsonl` | ✅ incl. `context_window` from session meta |
| Generic JSONL | any file, best-effort | ✅ role/type heuristics |

`CTXLENS_HOME` redirects discovery (tests, portable installs).

## How this is different

- **vs. your agent's `/context`** — that's a single in-session snapshot. ctxlens
  works across sessions, ranks the offenders, and does compaction forensics.
- **vs. usage monitors** — they track money and quota. ctxlens tracks
  *anatomy*: what the window is made of and where it went.
- **vs. sending logs to a cloud** — ctxlens would rather stay home. It's
  local-first because the question "what did my agent read" deserves a local
  answer.

## Roadmap

- [ ] OpenCode adapter
- [ ] `ctxlens watch` — live window gauge during a session
- [ ] Cross-session drift report (same repo, week over week)
- [ ] Flamegraph view of nested tool results

## License

[MIT](LICENSE)
