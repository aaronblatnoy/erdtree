# Phase 1 — Streaming Responder Adapter (evidence)

Date: 2026-06-21
Slice: core/model/ollama.py + tests/test_streaming.py ONLY (no other files touched).

## What changed

core/model/ollama.py (additive + one no-behavior-change refactor):
- NEW `_StreamAccumulator` class: single source of truth for collapsing
  StreamChunks -> AssembledResponse (content_parts + tool-call delta accumulation
  by index + finish_reason). This is the SHARED helper — chat() and the streaming
  responder both feed chunks through it, so a tool call cannot be assembled
  differently in the two paths (no fork; plan §3 Phase 1 risk mitigated).
- `chat()` refactored to use `_StreamAccumulator` (the body's accumulation logic
  at old :307-339 moved verbatim into the helper). Behavior byte-identical —
  test_ollama_roundtrip.py stays green (43 passed / 1 skipped, unchanged).
- NEW `stream_responder(client, on_delta=None) -> Responder`: a callable
  `(messages, tools=None, tool_choice="auto", *, _http_factory=None)
  -> AssembledResponse` with the SAME signature/return as chat(). It drains
  `client.stream(...)` through `_StreamAccumulator`, and for each
  `chunk.content_delta` calls `on_delta(token)` BEFORE returning. Net effect:
  AssembledResponse identical to chat() PLUS a side-channel of content tokens.
- NEW `_safe_emit(on_delta, token)`: wraps the sink call; ANY exception (or a
  None sink) degrades to no-stream and never aborts assembly. After a fault it
  stops re-attempting emits for the rest of the turn.
- Type aliases `Responder` / `OnDelta` for the loop/main to wire (factory ready
  for P2's incremental IO hook).

## Invariants threaded

- I1 — streaming talks only to localhost. The responder opens NO socket and
  names NO host; it calls `client.stream()`, which is loopback-asserted at the
  OllamaClient's construction (`_assert_localhost` at :47, asserted in
  `__init__`). Test `TestI1NoNewSocket` proves the injected factory is the only
  transport invoked and the endpoint carries the loopback host.
- SC4 — PRESENTATION ONLY. A streamed token is content ONLY (never an
  unconfirmed write). The loop still receives a full AssembledResponse-equivalent
  BEFORE routing/gating/dispatch. No audit.write / permissions.classify / gate
  ordering touched (those files were not opened). Parity tests prove the router/
  gate/audit see the SAME assembled turn they see today.
- BACK-COMPAT — buffered chat() + ConsoleIO path is unchanged and stays the
  default. Streaming is additive + injectable; a None on_delta degrades to
  today's buffered behavior (`test_none_sink_degrades_to_buffered`).
- I2 — no NEW user-facing strings are emitted by the responder (it only forwards
  model content tokens). `TestI2NoAiLanguage` documents/guards that any future
  progress wording added here must pass `core.agent.prompt._assert_no_ai_language`
  (imported, not re-listed).
- I9 — shell/shell.py byte-untouched; no new unbounded wait introduced; the
  responder never swallows ConnectionError (it only wraps the on_delta sink, not
  the stream() transport).

## Validation — PARITY + emission

- `TestOnDeltaEmission`: a 3-content-delta + tool_call script -> on_delta called
  >= 3 times IN ORDER (`["one ","two ","three"]`).
- `TestParityWithChat`: stream_responder(...) == client.chat() over the SAME SSE
  script for the tool-call path, the English path, a mixed content+tool-call
  turn, and parallel (2-index) tool calls. Equality is full dataclass `==`
  (content + tool_calls + finish_reason).
- `TestSinkResilience`: a raising sink does NOT abort/corrupt assembly (still ==
  buffered); a None sink degrades to buffered.

## Test commands and results (real)

```
$ .venv/bin/python -m pytest tests/test_streaming.py -q
..........                                                               [100%]
10 passed in 0.04s

$ .venv/bin/python -m pytest tests/test_ollama_roundtrip.py -q
...........................................s                             [100%]
43 passed, 1 skipped in 0.08s

$ .venv/bin/python -m pytest -q
1829 passed, 14 skipped, 371 subtests passed in 5.35s
```

passed = TRUE: parity asserts green AND test_ollama_roundtrip.py green (chat()
byte-behavior untouched) AND full suite green.

## DEFERRED-TO-MOSSAD

- Live 7B/14B Ollama round-trip FEEL of incremental token rendering — needs a
  provisioned box with Ollama running a real model (qwen2.5:7b/14b). The unit
  layer proves transport correctness + parity with scripted/chunked-responder
  doubles; the live token-by-token "feel" cannot be exercised on this build host.
