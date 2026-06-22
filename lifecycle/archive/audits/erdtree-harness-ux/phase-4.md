# Phase 4 Evidence — Small-Model Tool-Use Discipline + Few-Shot

**Date:** 2026-06-21
**Phase:** P4 — PROMPT DISCIPLINE (independent, parallel with P1-P3 spine)
**Files touched:** `core/agent/prompt.py`, `tests/test_prompt_fewshot.py`

---

## Changes Made

### core/agent/prompt.py

Added two new constants after `_HOUSE_SYSTEM_PROMPT`:

1. **`_TOOL_USE_DISCIPLINE`** — tight tool-use guidance block (4 rules, ~534 chars):
   - Call a system operation when request needs a live fact or system action
   - Answer directly when it is a plain question answerable from context
   - Never narrate; be terse; one operation at a time when unsure

2. **`_FEW_SHOT`** — two tight examples (~400 chars):
   - Example 1: "is nginx running?" → services tool call `{"operation": "status", "unit": "nginx.service"}`
   - Example 2: "what is the default SSH port?" → "Port 22." (direct answer, no tool call)

3. **`_FEW_SHOT_TOOL_CALL_EXAMPLE`** — structured dict for wire-shape parity test:
   ```python
   {"tool": "services", "arguments": {"operation": "status", "unit": "nginx.service"}}
   ```

Both `_TOOL_USE_DISCIPLINE` and `_FEW_SHOT` are checked by `_assert_no_ai_language` at import time (same as `_HOUSE_SYSTEM_PROMPT`). Any I2 violation fails the build at import.

Both are assembled into the system message in `assemble_messages()` as additional `system_parts`, between the house prompt and the tier addendum.

---

## I2 Compliance

All new strings are I2-clean. Verified three ways:
1. Import-time `_assert_no_ai_language` on each constant (build fails instantly on violation)
2. `test_discipline_constant_no_forbidden_terms` and `test_fewshot_constant_no_forbidden_terms` belt-and-suspenders assertions in the test file
3. `test_assembled_system_no_forbidden_terms` checks the full assembled system message

Forbidden terms avoided: "ai", "llm", "model", "agent", "neural", "machine learning", "gpt", "ollama", "inference" — none appear in any new string.

---

## Wire-Shape Parity

The `_FEW_SHOT_TOOL_CALL_EXAMPLE` dict is passed through `router.validate_arguments(SERVICES_SPEC, args)` in the test. This asserts:
- The `operation` value ("status") is a real op in `SERVICES_SPEC`
- The `unit` arg is present and typed correctly (str)
- No extra/unknown args
- The operation is `OpClass.READ` (the illustrative example picks a read-only op)

If the services spec changes (operation renamed, arg renamed) this test fails immediately.

---

## Test Results

```
.venv/bin/python -m pytest tests/test_prompt_fewshot.py -q
23 passed in 0.04s

.venv/bin/python -m pytest tests/test_snapshot.py -q
48 passed, 2 skipped in 0.05s

.venv/bin/python -m pytest -q
1819 passed, 14 skipped, 371 subtests passed in 5.31s
```

All pre-existing tests remain green. 23 new tests added.

---

## Deferred

**DEFERRED-TO-MOSSAD:** Live round-trip to verify that a real 7B/14B Ollama model actually picks the `services` tool and produces the correct wire format when prompted with "is nginx running?" — requires a provisioned Linux box with Ollama running a real model. Not performable on this dev host.

---

## New User-Facing Strings (I2 inventory for P6)

All strings below passed `_assert_no_ai_language`.

**_TOOL_USE_DISCIPLINE:**
- "Tool-use rules:"
- "Call a system operation when the request requires an action on this host or needs a live fact from it (service state, package version, disk usage, log lines, network status)."
- "Answer directly in English when the request is a plain question you can answer from the SYSTEM CONTEXT block or from general Linux knowledge."
- "Never narrate that you are about to do something.  Do the work or give the answer — nothing else."
- "Be terse.  One operation at a time when the next step depends on the result of the current one."

**_FEW_SHOT:**
- "FEW-SHOT EXAMPLES"
- "Example 1 — request that needs a live system fact (use the services operation):"
- "  Operator: is nginx running?"
- "  Correct response: call the services tool with {\"operation\": \"status\", \"unit\": \"nginx.service\"}"
- "Example 2 — plain question answerable from context or Linux knowledge (answer directly, no tool call):"
- "  Operator: what is the default SSH port?"
- "  Correct response: Port 22."
