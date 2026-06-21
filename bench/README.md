# Tool-Call Reliability Benchmark (seed)

Phase 0 scaffolding. The full runner (`bench/run_bench.py`) lands in Phase 4. This file fixes the
**validity-rate definition** and seeds ~10 cases so Phase 4 measures against a frozen target.

## What this measures (the #1 technical bet — decision #2)

The **tool-call validity rate**: across N agentic turns where the agent is expected to act, what
fraction emit a **valid, well-formed, parseable tool call** in the frozen protocol
(`docs/decisions/0002-tool-call-protocol.md`).

This is NOT "did the task succeed end-to-end" and NOT "was it the semantically best tool". It is
purely: *did the model speak the contract correctly so `router.py` can dispatch without a re-ask?*
Reliability of the wire format is the bet; correctness of intent is a separate (later) axis.

## Validity definition (frozen, per 0002 §2/§5)

A turn is **VALID** iff ALL hold:
1. The assistant turn contains ≥1 `tool_calls[]` entry with `type == "function"`.
2. `function.name` matches a registered tool id (the Phase-2 registry).
3. `function.arguments` parses as JSON (it is a JSON-encoded **string**, not a nested object).
4. The parsed arguments validate against that tool's JSON-Schema parameter schema (required fields
   present, types correct, enums respected, no rogue `additionalProperties`).

A turn is a **MISS** if any of the above fails, including:
- Prose / English answer where a tool call was required (the dominant 3B failure mode).
- Unknown / hallucinated tool name.
- `arguments` not valid JSON, or wrong/missing/extra fields vs the schema.
- A code-fence or pseudo-tool-call that is not in the `tool_calls[]` channel.

```
validity_rate = valid_turns / total_action_turns
```
Only "action turns" (the expected-tool-call set below) count toward the denominator. A correctly
emitted *English answer* on a turn that should be English is not in scope here.

## Targets (SC2)

- **Radagon base (Qwen2.5 7B / 14B-Instruct): >= 99.5%** — the ship gate for v0.1's primary tier.
- **Marika base (Qwen2.5 3B-Instruct): recorded, not gated.** Phase 4 records the 3B rate and emits
  an explicit GO / HOLE verdict for the Marika story (decision #2, open question Q2). If the 3B
  can't drive the loop, Marika ships reduced or waits for the fine-tune — surfaced, not absorbed.

A MISS below target does NOT block v0.1 (base-model ship is acceptable by decision); it is recorded
loudly as a deferred-to-Phase-10 item. Phase 10 (behavioral fine-tune) exists to close this gap to
the >=99.5% bar for v1.0.

## How a case is scored (Phase-4 runner contract)

Each `cases/*.json` is one scenario: a system + user prompt (with an injected system-context stub),
the tools advertised, and the expected outcome. The runner:
1. Assembles the prompt per 0002 §1 (tools advertised as JSON-Schema functions).
2. Streams from local Ollama (`/v1/chat/completions`, `stream:true`), assembles tool-call deltas
   per 0002 §4.
3. Applies the VALID/MISS test above.
4. Aggregates `validity_rate` per model size; the 3B run additionally yields the GO/HOLE verdict.

Run each case M times (temperature-varied) to get a stable rate; report mean + worst-case.

## Case schema

```json
{
  "id": "svc-restart-001",
  "domain": "services",
  "turn_type": "action",            // "action" = a tool call is expected; counts toward denominator
  "system_context": "distro=Rocky 9; nginx.service: failed; ...",  // injected per I5 (stub)
  "user": "restart nginx",
  "tools": ["services"],            // tool ids advertised (schemas from the Phase-2 registry)
  "expect": {
    "tool": "services",
    "arguments_contains": { "operation": "restart", "unit": "nginx.service" },
    "permission_class": "write"     // cross-check vs Phase-1 classifier (informational, not scored here)
  },
  "notes": "Canonical write-confirm path."
}
```

`arguments_contains` is a subset check used to sanity-confirm the model targeted the right thing; it
does not change the validity score (validity is purely format/schema). `permission_class` documents
the expected gate for cross-referencing Phase-1 tests; it is not part of the validity rate.

## Seed cases

`cases/` holds ~10 seed scenarios spanning the three Phase-2 core tool domains (services, packages,
logs) plus the read/write/destructive permission spectrum and two deliberate negative-control
("should stay English") turns. Phase 4 expands this into the full representative set.
