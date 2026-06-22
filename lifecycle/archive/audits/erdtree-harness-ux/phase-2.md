# Phase 2 — ReplIO incremental hook + stream drain

Scope (single-writer): edited ONLY `core/agent/repl.py`, `tests/test_streaming.py`,
and the `FakeIO` in `tests/test_repl.py`. No edits to main.py (build_repl wiring is
P3's seam — run_turn stays unaware of streaming vs buffered).

## What changed

### core/agent/repl.py
1. ReplIO Protocol extended with OPTIONAL hooks: `render_delta(token)`,
   `tool_step(text)` (P3), `tool_step_result(text)` (P3). Documented as
   feature-detected; an IO implementing only render()/confirm()/confirm_typed()
   (today's contract) still works because the streaming responder OWNS the delta
   sink and a buffered responder produces no deltas.
2. ConsoleIO implements `render_delta`: writes the token with NO trailing newline
   + `flush=True` (live tokens). Accumulates streamed content in `self._streamed`.
3. NO-DOUBLE-RENDER resolved in ConsoleIO.render(): if the same content was
   already streamed, render() emits ONLY a trailing newline and returns (no
   re-print). On the buffered path (`_streamed == ""`) render() prints the full
   English answer exactly as today — byte-identical.
4. run_turn's turn-final render is wrapped in `_safe_render()`: a presentation
   fault (e.g. a streaming sink that raised) is swallowed so the turn still
   completes and runs its memory/audit bookkeeping (mirrors P1's `_safe_emit`
   wrap on the delta sink). No audit.write added/moved/removed; gate ordering
   untouched (SC4).

### tests/test_repl.py
FakeIO gains `render_delta` + `self.deltas` capture. Existing `self.rendered`
behavior preserved (all 10 test_repl.py tests stay green).

### tests/test_streaming.py
Added `TestPhase2ReplStreaming` (5 tests) wiring stream_responder's on_delta to a
ReplIO.render_delta through a REAL Repl over an injected SSE script (I1:
loopback-asserted OllamaClient, no socket):
- SC1: deltas at the IO == the content-delta sequence, in order.
- NO-DOUBLE-RENDER (FakeIO): streamed == final_text; final_text NOT in rendered.
- NO-DOUBLE-RENDER (real ConsoleIO via capsys): stdout == answer + exactly one
  newline (answer count == 1, not 2).
- BACK-COMPAT: buffered ConsoleIO.render() prints full answer as today.
- DEGRADE: a render_delta that RAISES -> turn still ends in English, final_text
  correct, dispatched read still audited (SC4 spine intact).

## Invariants
- I1: no new socket / host. The streaming path reuses the loopback-asserted
  OllamaClient + stream(); tests inject `_http_factory`.
- I2: no NEW user-facing prose strings. render_delta forwards model content
  tokens only; the no-op close emits a bare newline. The phase-1 string guard
  (`running:`, `done`, `exit 0`, `not run`) still passes.
- SC4: streaming is presentation-only; no audit.write / permissions.classify /
  gate-ordering change. DEGRADE test proves the audit spine survives a render
  fault.
- BACK-COMPAT: buffered responder + ConsoleIO path is the DEFAULT; all existing
  tests green.

## Tests (real pass lines)
- `.venv/bin/python -m pytest tests/test_repl.py -q`        -> 10 passed
- `.venv/bin/python -m pytest tests/test_streaming.py -q`   -> 15 passed
- `.venv/bin/python -m pytest tests/test_invariance_baseline.py -q` -> 5 passed
- Full suite `.venv/bin/python -m pytest -q` -> 1834 passed, 14 skipped,
  371 subtests passed.

## Deferred
- LIVE 7B/14B Ollama round-trip FEEL of incremental token render: DEFERRED-TO-MOSSAD
  (needs a provisioned box + Ollama running a real model). Unit-provable here via
  scripted chunked-responder doubles; the live feel is not.
