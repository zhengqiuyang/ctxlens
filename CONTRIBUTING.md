# Contributing to ctxlens

Thanks for looking under the hood. ctxlens is a small tool with a strict spine —
these rules keep it that way.

## The three laws

1. **Zero LLM in the analysis path.** No network calls, no model inference, ever.
   Every number in a report must be reproducible from the session file alone.
2. **Zero dependencies.** The package imports nothing outside the standard
   library. `pytest` is the only dev dependency.
3. **Tolerant parsing.** An adapter may warn about a line it does not
   understand; it must never crash on one. Agent log formats drift every
   release — unknown shapes are counted, not fatal.

## House style

- `src/` layout, one concept per module, type hints on public functions.
- Determinism is a feature: no timestamps, no randomness, no locale-dependent
  formatting anywhere in rendered output. Tests rely on it.
- The token estimator is a documented heuristic, not a secret. If you improve
  its accuracy, update the honest-error note in the README and add fixtures.
- Every new adapter needs: a fixture file built from a real session (secrets
  scrubbed), a test, and an entry in the README adapter table.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

CI runs on Linux, macOS and Windows across Python 3.9–3.13. `pathlib.Path.home()`
discovery is redirected by `CTXLENS_HOME`, so tests never touch a real home
directory.

## Reporting a format drift

If ctxlens suddenly reports `skipped N unreadable lines` for a tool that used
to parse cleanly, open an issue with:

1. the tool name and version,
2. one sample line (**scrubbed** — no code, no prompts, no paths),
3. the warning text.

PRs welcome. Small and sharp beats big and vague.
