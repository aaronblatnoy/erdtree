# Phase 5 — RE-ASK TIGHTENING — Audit Evidence

**Executed:** 2026-06-21
**Scope:** `core/agent/router.py` and `tests/test_router.py` only.
**Status:** COMPLETE — all tests green.

---

## What Changed

### `core/agent/router.py` — re-ask wording (lines 58-103)

Three re-ask functions made more instructive for small-model self-correction.
TurnKind classification, is_valid_action predicate, and the role:"tool" +
tool_call_id message SHAPE are **byte-unchanged** (FROZEN CONTRACT).

#### `reask_invalid_arguments(tool, detail)`

**Before:**
```
The `{tool}` tool was called with invalid arguments: {detail}.
Please rewrite the input so it satisfies the expected schema.
```

**After:**
```
The `{tool}` tool was called with invalid input: {detail}.
Rewrite the input so it matches the required schema and try again.
```

The `detail` parameter already threads the exact validator message
(e.g. `"'operation' must be one of [disable, enable, ...], got 'instal'"`)
from `validate_arguments`. The new wording leads with "invalid input" and
ends with an explicit "try again" instruction.

#### `reask_unknown_tool(name, valid_tools=None)`

**Before:**
```
Unknown tool: {name}
```

**After (no list):**
```
'{name}' is not a recognised tool.
```

**After (with list):**
```
'{name}' is not a recognised tool. Use one of the available tools: {names}.
```

The Router now passes `self._registry.list_tools()` at the call site for
unknown-tool misses so the next call can pick a valid tool name. The
`valid_tools` parameter is optional (default `None`) for backward compat
with callers that don't have registry access.

#### `reask_invalid_input(detail)`

**Before:**
```
Invalid tool input: {detail}
```

**After:**
```
The tool input could not be parsed: {detail}.
Check that the input is valid JSON and try again.
```

Surfaces the offending detail and provides an explicit corrective instruction.

---

## I2 Compliance

All three new re-ask strings were verified against `_AI_PATTERN` from
`core.agent.prompt`. No forbidden terms appear (ai, llm, model, agent,
agentic, inference, ollama, neural, gpt, machine learning).

---

## Frozen Contract Verification

- `TurnKind` enum values: `TOOL_CALL="tool_call"`, `ENGLISH="english"`, `MISS="miss"` — **unchanged**.
- `is_valid_action` predicate: `kind is TOOL_CALL and not misses and bool(calls)` — **unchanged**.
- `reask_messages` shape: `role:"tool"` + `tool_call_id` — **unchanged**.
- `Router.route()` routing logic — **unchanged** except for passing the tool list to `reask_unknown_tool`.

---

## Tests Run

```
.venv/bin/python -m pytest tests/test_router.py -q
29 passed in 0.08s
```

**New assertions added (10 new tests):**
- `test_bad_operation_enum_reask_contains_valid_ops_list` — re-ask for bad op enum contains the valid ops list and the offending value.
- `test_bad_operation_enum_reask_passes_i2` — invalid-arguments re-ask passes `_AI_PATTERN`.
- `test_unknown_tool_reask_names_offending_tool` — unknown-tool re-ask names the bad tool.
- `test_unknown_tool_reask_lists_valid_tools` — unknown-tool re-ask lists registered tool names.
- `test_unknown_tool_reask_passes_i2` — unknown-tool re-ask passes `_AI_PATTERN`.
- `test_reask_invalid_arguments_standalone_i2` — standalone I2 check for `reask_invalid_arguments`.
- `test_reask_unknown_tool_standalone_i2` — standalone I2 check for `reask_unknown_tool` (both forms).
- `test_reask_invalid_input_standalone_i2` — standalone I2 check for `reask_invalid_input`.
- `test_turnkind_classification_frozen` — TurnKind enum values unchanged.
- `test_is_valid_action_predicate_frozen` — is_valid_action predicate unchanged.

**Full suite:**
```
.venv/bin/python -m pytest -q --tb=short
1819 passed, 14 skipped, 371 subtests passed in 5.30s
```

---

## DEFERRED-TO-MOSSAD

Live 7B/14B Ollama round-trip FEEL: confirming that the tighter re-ask wording
actually causes a small base to self-correct within the round cap requires a
provisioned box with Ollama running a real 7B/14B model. This dev host has no
Ollama. Deferred to the benchmark/MOSSAD track (bench/, Phase-10).

---

**One-line summary:** Phase 5 complete — three re-ask strings tightened to surface
concrete validator detail (valid op enum, offending tool name, offending token),
all I2-clean, SHAPE unchanged; 10 new assertions + 29/29 test_router.py green,
1819/1819 full suite green.
