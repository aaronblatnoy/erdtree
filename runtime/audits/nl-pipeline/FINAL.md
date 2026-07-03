# NL Pipeline Buildout — Final Rollup

**Status:** COMPLETE  
**Plan archived:** `lifecycle/archive/plans/nl-pipeline-buildout.txt`

---

## Phase Outcomes

| Phase | Result | Notes |
|-------|--------|-------|
| P0 measure & decide | measurement-gap (mossad offline) | Conservative defaults: max_workers=1, no logprobs. Harness ready at bench/phase0_harness.py. Architectural decision not contingent on numbers. |
| P1 UnderstandingStrategy seam | PASS (clean: true) | 98 refactor-scope tests pass. One pre-existing unrelated failure in test_compaction.py (fails on unmodified main branch). Pure move — zero behavior change. |
| P2 deterministic assembler | PASS | 82 tests green. Convergence proof: disk.format → mkfs.ext4 /dev/sdb → DESTRUCTIVE → CONFIRM_TYPED matches native gate exactly. |
| P3 intent classifier | PASS | 53 tests green. Two backends (embedding similarity + narrow model call) behind one injected interface. Stub-embedder for dev-host testing. |
| P4 slot extraction | PASS | 18 tests green. 984 existing tests remain green. Deterministic-first + parallel model workers; deterministic slots resolve without responder invocation. |
| P5 wiring | PASS | 42/42 tests green (convergence + repl + integration invariance + baseline). FastThenDecomposeStrategy: native path runs first, decomposition only fires on MISS. ERDTREE_UNDERSTANDING env flag gates mode selection. |
| P5v gate-convergence audit (hard stop) | **PASS** (audit-duo, converged, 0 rounds cross-examination) | Alpha: 0.97 confidence. Beta: 0.96 confidence. 32/32 tests green. No bypass found. See full audit report in workflow output. |
| P6 verification + retry | PASS | destructive_never_retries=true. Idempotent retry capped at ERDTREE_RETRY_MAX (default 2). Every verification read audited. |
| P7 fallback | PASS | 42 tests green. source=fallback in audit record. Nothing from fallback auto-runs. |
| P8 compound planning | PASS | Heuristic compound detector (conjunctions + verb/object pairs) before model. Static planning shown before any step runs. Dynamic re-plan only on verification invalidation. |
| P9 man-page breadth track | PASS | 40 tests green. tools/manpage/{parse,generate_schemas}.py + models/schemas/manpages.v1.json. Generated tools registered ALWAYS-GATED, version-pinned to package NEVRA. |

---

## Hard Gates

**P5v (no-bypass audit):** PASS — both independent auditors converged. No code path in `core/agent/pipeline/` reaches `registry.dispatch` without first passing through `permissions.classify` on the same synthesized argv. Destructive intents gate identically to native (CONFIRM_TYPED interactive, REFUSE non-interactive).

**P6 (destructive-never-retry):** PASS — destructive ops escalate to user, no retry branch exists in that path.

---

## Latency Checkpoints

- **Checkpoint A (P0, mossad):** DEFERRED — mossad offline at measurement time. Harness at `bench/phase0_harness.py`. Run when mossad comes back: `ssh mossad "cd ~/erdtree && python bench/phase0_harness.py"`. Update `runtime/audits/nl-pipeline/phase-0-measurements.md`.
- **Checkpoint B (P5, common op):** Common ops run native path first (FastThenDecomposeStrategy); decomposition never fires on a clean match → common-op p50 equals native by construction. See `runtime/audits/nl-pipeline/phase-5-latency.md`.
- **Checkpoint C (P6, verify round-trip):** Documented in phase-5-latency.md.

---

## Keep-Stale Status

The native code path in `repl.py` is byte-identical and remains the default. `Repl.__init__` assigns `NativeToolCallStrategy` when no `strategy` arg is supplied. The new pipeline is activated only via `ERDTREE_UNDERSTANDING=decomposed|fast-then-decompose` env flag. Five frozen invariance baseline scenarios pass with unchanged audit/outcome oracles.

---

## What Was Built

```
core/agent/pipeline/
  __init__.py          — package, exports strategy types
  strategy.py          — UnderstandingStrategy Protocol, NativeToolCallStrategy,
                         DecomposedStrategy, FastThenDecomposeStrategy
  assembler.py         — deterministic (tool, op, slot_values) → ParsedCall | Unresolved
  intent.py            — classify_intent → IntentMatch | NoConfidentMatch
  slots.py             — deterministic-first + parallel model workers → slot dict
  verify.py            — post-exec state check + op-class-keyed retry
  fallback.py          — last-resort free-text path, visually marked, always gated
  plan.py              — compound detection + static planning + bounded dynamic re-plan

tools/manpage/
  parse.py             — troff/mandoc parser (build-time only)
  generate_schemas.py  — emits OpSpec/ArgSpec in frozen core/tools shape

models/schemas/
  manpages.v1.json     — versioned schema artifact

docs/decisions/
  0004-understanding-strategy.md  — Option C rationale, escalation-tier posture

bench/
  phase0_harness.py    — latency/concurrency/logprob measurement harness for mossad
```

**309 tests green** across all new pipeline test suites.
