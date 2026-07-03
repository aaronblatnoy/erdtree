# 0004 — Understanding Strategy: Decomposed Pipeline as Escalation Tier (DRAFT)

- Status: DRAFT — pending Phase-0 concrete measurements from mossad
- Date: 2026-07-01
- Phase: NL Pipeline Buildout, Phase 0 (measurement + decision)
- Read by: Phase 1 (repl.py seam), Phase 2 (assembler), Phase 3 (intent),
           Phase 4 (slots), Phase 5 (wiring + escalation), Phase 6 (verify),
           Phase 7 (fallback), Phase 8 (compound planning)
- Coexists with: 0002 (FROZEN tool-call protocol — NOT replaced or modified)
- Gates: Phase 1 prerequisite is Phase-0 GO. This doc is a draft until
         runtime/audits/nl-pipeline/phase-0-measurements.md is updated with
         concrete numbers and a GO verdict.
- Scope: framework-level.  No tier/product names.  I6.

---

## Problem

A 3B (small-tier) or 7-14B (mid-tier) base is unreliable at emitting a
complete, schema-valid tool call for an arbitrary request in ONE turn.  Today
the "understanding" step is a single `responder(messages, tools)` call
classified by `core/agent/router.py`.  When it misses, the loop re-asks the
SAME hard question.

The failure modes are well-characterized:
- Prose where a tool call was required (the dominant small-model failure).
- Unknown tool name (hallucinated).
- Unparseable or schema-invalid arguments (required slot missing or mistyped).

Fixing this at the model level (fine-tuning) is orthogonal and future work.
This decision records the framework-level strategy to improve reliability NOW
by restructuring the "understanding" step — without replacing or weakening the
execution half.

---

## The Non-Problem (existing execution half is correct)

The execution half is **already built and correct**:

- `core/tools/__init__.py::run_subprocess` is `subprocess.run(list)`, shell-free.
- `core/agent/permissions.py::classify` is the hardened, argv-aware, default-deny
  gate.  READ → ALLOW, WRITE → CONFIRM, DESTRUCTIVE → CONFIRM_TYPED,
  non-interactive write/destructive → REFUSE.
- `core/agent/repl.py::run_turn` is the audit + gate + dispatch spine.

The durable work is concentrated in the **understanding** step (intent +
slot extraction) and **deterministic verification** post-execution.  Building
a second executor or a second gate would be a risk, not an improvement.

---

## Options Considered

### Option A — Replace router.py (rejected)

Rewrite or replace the Router and the frozen 0002 tool-call contract to
structurally prevent misses.  Rejected because:

- 0002 is **FROZEN** and byte-compatible with Ollama's `/v1/chat/completions`.
  Breaking it breaks training data alignment (Phase 10).
- The Router is the single source of truth for VALID/MISS; replacing it would
  orphan the existing bench/validity measurement.
- The reliability problem is in the understanding STEP, not the wire format.

### Option B — Second executor (rejected, R1)

Build an alternate execution path that bypasses or supplements `_dispatch_calls`.
Rejected because:

- Any path that reaches `registry.dispatch` without first passing through
  `permissions.classify` on the same synthesized argv is a security regression.
- This is Risk R1 in the plan — the highest-rated risk — and is the exact
  failure mode of "just run it and see".
- The existing gate is the product's hardened invariant (I3).  A second gate
  would drift from it.

### Option C — Converge on the spine (SELECTED)

Add an isolated, opt-in "decomposed understanding" strategy that:

1. Runs as an **escalation tier** behind today's single-shot fast path.
2. Decomposes understanding into: intent classification → narrow per-slot
   extraction → deterministic assembly → validated `ParsedCall`.
3. The `ParsedCall` it produces is the **SAME frozen shape** the native path
   produces (0002 §2/§5: call_id, tool, operation, args, permission_class).
4. That `ParsedCall` flows into the **UNCHANGED** hardened spine:
   `synthesize_command → permissions.classify → _resolve_gate → registry.dispatch
   → AuditLog.write`.

The decomposed strategy NEVER dispatches, NEVER gates, NEVER audits — those are
exclusively the spine's responsibility.  The strategy's output is a `ParsedCall`;
the spine does the rest identically for both the native and decomposed paths.

---

## Architecture (Option C)

```
user_input
    |
Repl.run_turn (core/agent/repl.py)            ← ONE integration seam
    |
+---+-------------------------------+
|  UnderstandingStrategy.propose(...)  |      (NEW protocol, Phase 1)
+---+-------------------------------+
|                                   |
[default] NativeToolCallStrategy    [opt-in] DecomposedStrategy
  responder(messages, tools)          core/agent/pipeline/  (NEW, Phases 2-4)
  Router.route()                        [1] intent classifier
  byte-identical to today               [2] parallel slot extraction
    |                                   [3] deterministic assembler
    |                                        → emits ParsedCall(s)
    +-------------------+-------------------+
                        |
              list[ParsedCall]  (SAME shape, both strategies)
                        |
   ===== UNCHANGED HARDENED SPINE (repl._dispatch_calls) =====
     synthesize_command(call)     (repl.py, reused verbatim)
        → permissions.classify(argv, ExecContext)   [THE ONLY GATE — I3]
        → _resolve_gate  (ALLOW / CONFIRM / CONFIRM_TYPED / REFUSE)
        → registry.dispatch(tool, op, args)         [subprocess.run(list)]
        → AuditLog.write                            (I4, every op)
                        |
   [6] verification (Phase 6): a READ op via the SAME spine,
       compared to intended state; bounded retry keyed on OpClass;
       destructive → escalate, never auto-retry
                        |
             English answer terminates the turn
```

---

## Escalation-Tier Posture

The decomposed strategy is an **escalation tier**, not the default.

- Fast path (today): `NativeToolCallStrategy` → single `responder()` call.
  This path is **never touched** by decomposition.  Common-op p50 is
  structurally invariant (I8: reads feel instant).
- Escalation trigger: a MISS from the native path (no valid `ParsedCall`
  returned), OR a `NoConfidentMatch` from the intent classifier.
- Escalation cost: the sum of intent + slot-worker + assembler calls.
  This is only paid when the fast path already failed; it cannot regress
  the common-op latency.

Env-flag control (opaque in main.py — I6):
- `ERDTREE_UNDERSTANDING=native` (default — today's behavior, no change)
- `ERDTREE_UNDERSTANDING=fast-then-decompose` (escalation tier — Phase 5+)
- `ERDTREE_UNDERSTANDING=decomposed` (always-on — bench/testing only)

The default is flipped to `fast-then-decompose` ONLY after Phase-5 mossad
latency checkpoint confirms common-op p50 is unchanged.

---

## Coexistence with 0002 (FROZEN contract)

0002 is **not replaced, not modified, not weakened**.

The decomposed strategy is a USER of 0002, not a replacement:

- The assembler (Phase 2) calls `router.validate_arguments` (the frozen
  validator) and `spec.permission_class_for(operation)` (the frozen gate
  class assignment).  One validator, not two.
- The output `ParsedCall` is the frozen 0002 shape (call_id, tool, operation,
  args, permission_class) — the same shape `Router.route()` produces.
- `synthesize_command` and `permissions.classify` see the same `ParsedCall`
  regardless of which strategy produced it.

The bench's VALID/MISS predicate (delegated to `Router.route`) is unchanged.
The decomposed strategy is scored on the same predicate.

---

## Invariants This Decision Preserves

| Invariant | How this decision preserves it |
|-----------|-------------------------------|
| I1 No egress | Every extra inference call is localhost Ollama via the injected responder. N slot calls = N × local compute. |
| I2 No AI language | Plan/confirm/verify surfaces speak plain Linux; the strategy label ("native"/"decomposed") is internal only. |
| I3 Single gate | `permissions.classify` is the ONLY gate. The pipeline has no dispatch code; it returns `ParsedCall`. The convergence test (Phase 5) hard-gates on this. |
| I4 Audit every op | Every attempted op (incl. verification reads, fallback attempts, misses) writes exactly one append-only JSONL record. `source` field added (additive). |
| I5 Fresh context | Context injected every turn; invalidated after a successful mutation (verification reads must see post-mutation reality). |
| I6 No tier names | TierConfig is injected; slot-worker cap is a config field; no tier/product names in pipeline code. |
| I7 Shared architecture | Marika (3B) and mid-tier (7-14B) share one architecture. Difference is model size + slot-worker depth + escalation ladder, not structure. |
| I8 Reads feel instant | Decomposition never fires on the fast path (escalation-tier posture). Common-op p50 is structurally protected. |

---

## Open Questions Resolved by Phase-0 Measurements

The following questions are recorded as OPEN pending the mossad measurements.
This doc will be finalized once `runtime/audits/nl-pipeline/phase-0-measurements.md`
is updated with concrete numbers.

**Q1 (Phase-0 primary):** Does Ollama on 2x3060 Ti decode slot workers
concurrently or serialize them?

- If concurrent (speedup >1.3x at some NUM_PARALLEL): Phase 4 may use a thread
  pool of K workers capped at NUM_PARALLEL.  The escalation cost is bounded by
  the SLOWEST slot (not the sum).
- If serial (speedup ≈ 1.0): Phase 4 MUST prefer deterministic slot extraction
  and cap model slot-workers hard (1 or 2).  The reliability win survives serial;
  only the escalation latency is higher.  The escalation-tier posture makes this
  acceptable (it only fires on MISS).

**Q2 (Phase-0 / Phase-3):** Any usable confidence/logprob from the endpoint?

- If logprobs are present: use them as a coarse confidence signal for intent
  match (supplementing intent-distance + slot-completeness).
- If absent (Assumption A2 in the plan): confidence is synthesized from
  concrete deterministic signals only.  Self-consistency sampling is the
  fallback but costs N more calls per turn (weigh against I8).

**Q3 (Phase-3):** Intent via sqlite-vec embeddings (0003 reuse) vs a model
call?  Phase-3 spikes both behind the same interface; this decision records
that both are valid and the seam is identical either way.

---

## Pending Measurements

This document is a **DRAFT** until the Phase-0 mossad measurements are complete.

When measurements are available, update:
1. `runtime/audits/nl-pipeline/phase-0-measurements.md` — concrete numbers.
2. This document — fill in the Q1/Q2 answers and finalize status to ACCEPTED.
3. Phase-4 brief — set `max_workers` based on Q1 answer.
4. Phase-3 brief — set intent backend based on Q2 answer.

The architectural decision (Option C, escalation-tier posture, convergence on
the frozen spine) is NOT contingent on the measurements.  The measurements
inform implementation details (slot-worker cap, confidence mechanism); they do
not change the selected option.
