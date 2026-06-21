# Phase 3 Audit Evidence — Ollama Client + Prompt Assembly

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Deliverables

| File | Status |
|------|--------|
| `core/model/ollama.py` | CREATED |
| `core/agent/prompt.py` | CREATED |
| `core/model/__init__.py` | CREATED (empty, makes package) |
| `tests/test_ollama_roundtrip.py` | CREATED |

## Test Results

```
43 passed, 1 skipped in 0.16s
```

All mock tests green. 1 test (`TestDeferredToMossad::test_live_tool_call_round_trip`)
is correctly skipped with `DEFERRED-TO-MOSSAD` — requires live Ollama + pulled model
on the Mossad server.

## Invariant compliance

### I1 — Localhost-only egress
- `_assert_localhost()` in `core/model/ollama.py` parses the configured `base_url`
  and resolves the host to IP. Raises `EgressViolation` for any non-loopback address
  (public IPs, private IPs, external hostnames).
- Called at `OllamaClient.__init__` — no instance can be constructed pointing to a
  non-localhost endpoint.
- Tested by `TestEgressGuard` (8 cases): localhost/127.0.0.1/::1 accepted;
  8.8.8.8, 192.168.1.100, example.com all raise `EgressViolation`.

### I2 — No AI language in user-facing strings
- `_assert_no_ai_language()` in `core/agent/prompt.py` scans text for a forbidden
  term set (`{"ai", "llm", "model", "agent", "neural", "ollama", ...}`) with
  whole-word, case-insensitive matching.
- Applied at import time to the house system prompt (fails fast if the module
  itself is the violator).
- Applied at `assemble_messages()` call time to `tier_prompt` supplied by the caller.
- Tested: `TestPromptAssembly::test_ai_language_check_fires_on_forbidden_term` and
  `test_tier_prompt_with_ai_language_rejected`.

### I5 — System context always injected
- `assemble_messages()` always includes a `SYSTEM CONTEXT` block in the system
  message, populated from the caller's `snapshot_text` (the output of
  `SystemSnapshot.to_prompt_text()`).
- If `snapshot_text` is empty, a placeholder "(Context collection unavailable for
  this turn.)" is injected — the block is never absent.
- Tested: `test_snapshot_text_in_system_message` and `test_missing_snapshot_produces_placeholder`.

### I6 — No tier/product names in core/
- `core/model/ollama.py`: zero hardcoded tier or product names. Model tag and
  base URL come entirely from the caller-supplied `TierConfig`.
- `core/agent/prompt.py`: zero hardcoded tier or product names. Tier-specific text
  accepted as a `tier_prompt` argument from the caller (Phase 9 tier loader).
- Pinned-tag enforcement: `TierConfig` raises `ValueError` if model ends with
  `:latest` (CLAUDE.md gotcha, plan §2 new env vars).

## Wire format compliance (0002)

- `build_tool_list()` produces `{"type":"function","function":{name,description,parameters}}`
  matching 0002 §1 exactly.
- `OllamaClient.chat()` assembles SSE tool-call deltas by index, concatenating
  `function.arguments` across chunks, matching 0002 §4 frozen streaming-assembly rules.
- `AssembledResponse.tool_calls` entries carry `{"id", "name", "arguments"}` where
  `arguments` is a raw JSON string (not parsed) — matching 0002 §2 parse contract.
- `finish_reason` is forwarded verbatim (`"tool_calls"` / `"stop"`).

## End-to-end mock gate (Phase 3 primary gate)

`TestE2EMockRoundTrip::test_e2e_tool_call_round_trip`:
1. `assemble()` builds a full messages array from user input + snapshot text.
2. A mock HTTP factory returns SSE for a `services` tool call with arguments
   `{"operation":"status","unit":"postgresql.service"}` split across 4 deltas.
3. `OllamaClient.chat()` assembles the stream.
4. Assertions: `finish_reason == "tool_calls"`, 1 tool call, `name == "services"`,
   `json.loads(arguments)` succeeds, fields match expected values.

**PASSED.**

## Deferred

- Live base-Qwen round-trip: `TestDeferredToMossad::test_live_tool_call_round_trip`
  — requires Ollama + `qwen2.5:7b-instruct-q4_K_M` on the Mossad server.
  Run with: `pytest tests/test_ollama_roundtrip.py::TestDeferredToMossad -v`
  (remove the `skip` marker on Mossad).

## Files NOT touched

All existing Phase 1/2 files (`core/context/`, `core/agent/audit.py`,
`core/agent/permissions.py`, `core/tools/`) are unmodified.
