# Phase 6 — Integration Wiring + Invariance Proof (evidence)

Date: 2026-06-21
Host: Linux (Arch). Tests run with the project venv: `.venv/bin/python -m pytest`.

## What changed (single NEW write: core/agent/main.py)

`build_repl` (core/agent/main.py) now wires the **streaming** responder on the
live ConsoleIO path by default:

- New helper `_stream_enabled()` reads `ERDTREE_STREAM` OPAQUELY (default ON;
  `0/off/false/no` -> buffered; any unrecognized value -> default ON; never
  raises — I9).
- The `ConsoleIO` is built FIRST so its `render_delta` is the streaming sink.
- Default path: `responder = stream_responder(client, on_delta=io.render_delta)`
  (the P1 adapter over the loopback-asserted `OllamaClient.stream()` — I1, no
  new socket, no new host). It returns the SAME `AssembledResponse` `chat()`
  assembles from the same chunks (parity), so router/gate/audit see the
  identical assembled turn (SC4 — streaming is PRESENTATION ONLY).
- `ERDTREE_STREAM=0` falls back to the buffered `client.chat(...)` closure
  (SC5/back-compat). The Repl is now built with the pre-constructed `io`.

repl.py was READ/verify-only (its P2/P3 edits already landed). shell/shell.py
was NOT edited.

## I9 (dead-man) — VERIFIED, not edited

shell/shell.py `_run_english_turn` (shell.py:332-340) wraps `self._repl.run_turn`
and catches `ConnectionError` -> bash fallback. The streaming responder drains
`client.stream()`, whose `_make_request` raises `ConnectionError` on `URLError`
EXACTLY as `chat()` does (ollama.py:404) — same code path, no new timeout, no
new unbounded wait. The guard fires unchanged. Proven by:
- `tests/test_deadman.py` (run alongside) — 9 tests green.
- `test_streaming_responder_raises_connectionerror_when_unreachable` in the new
  file: a streaming responder over `127.0.0.1:1` raises `ConnectionError` on the
  first drain.

I9 is INTACT; no escalation.

## SC4 INVARIANCE PROOF

The Phase-0 oracle (`tests/test_invariance_baseline.py`) doubles + scenario
scripts are REUSED, not re-derived. The five canonical turns (READ,
CONFIRMED WRITE, DECLINED WRITE, DESTRUCTIVE wrong-word, MISS+re-ask) are
replayed through the FULLY-WIRED streaming seam
(`stream_responder(client, on_delta=io.render_delta)`, transport = injected SSE
script, loopback client, no socket) and asserted IDENTICAL to the pinned
"before" values, field-by-field:

- audit record COUNT + every `permission_decision` / `exit_code` / `tool` /
  `tier` / `result` prefix
- `TurnOutcome` (tool_calls_made, refused, misses, rounds, ended_in_english)
- `outcome.final_text` byte-identical to the frozen English answer
- NO-DOUBLE-RENDER: the streamed deltas reconstruct the answer and render()
  appends nothing additional.

SC4 equality assertion (representative), parametrized over all 5 scenarios:

    assert len(records) == len(sc["audit"])            # audit count identical
    assert rec["permission_decision"] == expected      # gate decision identical
    assert getattr(outcome, field) == val              # TurnOutcome identical
    assert outcome.final_text == sc["rendered"][-1]     # assembled answer identical
    assert "".join(io.deltas) == answer                 # operator sees it once
    assert answer not in io.rendered                    # NO-DOUBLE-RENDER

Result: all 5 scenarios GREEN -> gate/audit/dead-man byte-behavior UNCHANGED.

## SC3 consolidated I2 inventory

Every NEW user-facing string across P2/P3/P4/P5 is asserted to pass
`prompt._AI_PATTERN` (imported, terms NOT re-listed) AND `_assert_no_ai_language`:
- P3 step lines: `running: <cmd>`, `done`, `exit 0`, `exit 1`, `not run`.
- P5 re-asks (instantiated with real validator detail): `reask_invalid_arguments`,
  `reask_unknown_tool` (with/without tool list), `reask_invalid_input`.
- P4 operator-visible few-shot lines: `is nginx running?`,
  `what is the default SSH port?`, `Port 22.`.
The P4/P5 prompt prose is ALSO import-time asserted by `_assert_no_ai_language`
(build fails at import on violation) — confirmed: `core.agent.{main,prompt,router}`
import cleanly.

## DEV-HOST honesty

NO live Ollama round-trip. Every model turn is a scripted SSE byte-sequence via
the injected `_http_factory` seam; the loopback-asserted client never opens a
socket. Live 7B/14B incremental-render FEEL is reasoned + double-proven (parity
in test_streaming.py + this invariance equality) and the real round-trip is
**DEFERRED-TO-MOSSAD** (needs a provisioned box + Ollama running a real model).

## Test runs (real output)

    $ .venv/bin/python -m pytest tests/test_main.py tests/test_deadman.py -q
    16 passed in 0.12s

    $ .venv/bin/python -m pytest tests/test_integration_invariance.py -q
    20 passed in 0.10s

    $ .venv/bin/python -m pytest -q
    1862 passed, 14 skipped, 371 subtests passed in 5.58s

Full suite >= 1795 prior tests + the new Phase-6 tests: GREEN.
SC4 equality holds. test_main.py + test_deadman.py GREEN (I9 intact).
passed = true.
