# Phase-5 Latency Checkpoint (CHECKPOINT B) — NL Pipeline Buildout

**Date attempted:** 2026-07-01
**Executor:** Claude Opus (Phase-5 wiring subagent)
**Target host:** mossad (aaron@192.168.1.163 / Tailscale 100.94.62.115)
**Gates:** flipping `ERDTREE_UNDERSTANDING` default from `native` to
`fast-then-decompose` (Section 9, CHECKPOINT B).

---

## Status: LIVE NUMBERS DEFERRED — mossad OFFLINE at measurement time

Both paths timed out from the build host (same posture as
`phase-0-measurements.md`):

- `ssh mossad` (Tailscale 100.94.62.115 :22) — Operation timed out.
- No live Ollama endpoint reachable; per the bench honesty gate + I1 this note
  does **NOT** fabricate wall-clock numbers.

What IS established here without a live model:
1. The **common-op p50 == native p50** claim is proven **by construction**
   (below) and additionally pinned by the dev-host invariance suite.
2. The exact, copy-paste reproducible commands to capture the two required
   numbers on mossad are recorded (Recovery Steps).

---

## The two numbers this checkpoint requires (plan Phase 5, step 4)

| # | Measurement | Value |
|---|-------------|-------|
| B1 | p50 of a COMMON op under `fast-then-decompose` | **== native p50** (by construction; live confirmation DEFERRED) |
| B2 | p50 of a native COMMON op (baseline) | **DEFERRED** (needs mossad; == Phase-0 single-shot p50) |
| B3 | p50 of a HARD/compound op under decomposition (escalation cost) | **DEFERRED** (needs mossad) |
| B4 | Escalation delta (B3 − B1) | **DEFERRED** (derived once B1/B3 land) |

---

## B1 == B2 is structural, not empirical

The `fast-then-decompose` policy is expressed as ONE `UnderstandingStrategy`
(`core/agent/pipeline/strategy.py::FastThenDecomposeStrategy`). Per round it:

1. runs `NativeToolCallStrategy.propose(...)` — today's single-shot fast path,
   ONE `responder(messages, tools)` call, byte-identical to `native`; then
2. returns that native result **immediately** whenever native produced any valid
   call OR an English answer.

A COMMON op ("restart nginx", "is nginx failing") is exactly the case where
native yields a valid call or an English answer on the first round. So for a
common op the decomposed branch is **never entered**: the only model call on the
common path is the same single native call `native` makes. There is:

- no extra intent call,
- no slot-worker calls,
- no assembler round-trip on the hot path,

so the p50 for a common op under `fast-then-decompose` is the p50 of the native
single-shot turn — **identical wall-clock, same one round trip**. Decomposition
(the second, expensive tier) fires ONLY on a native MISS / no-valid-calls
(escalation), which by definition is not the common op (I8 preserved: reads /
common ops feel instant).

This is the same escalation-tier posture recorded in
`docs/decisions/0004-understanding-strategy.md` and
`phase-0-measurements.md` ("common-op p50 is structurally invariant").

### Dev-host evidence for the structural claim (no model needed)

`tests/test_pipeline_convergence.py::test_fast_path_returns_native_without_touching_decomposition`
proves the escalation strategy returns the native result and **never invokes the
decomposed strategy** when native yields a valid call (a recording stand-in
asserts `propose()` was not called). That is the machine-checked form of "the
common path does exactly one native model call, nothing more" — the necessary
and sufficient condition for B1 == B2.

The existing `tests/test_invariance_baseline.py` + `tests/test_integration_invariance.py`
additionally pin that the default (`native`) path is byte-identical (gate/audit/
outcome), so flipping the flag changes ONLY the escalation behavior on a miss.

---

## B3 (escalation cost) — what will be measured

The hard-op path is: native MISS -> `DecomposedStrategy` runs
`classify_intent` (1 narrow call OR a retrieval, no generation) + `extract_slots`
(deterministic-first; only genuinely fuzzy slots issue a narrow model call,
capped by `ERDTREE_SLOT_WORKERS`) + deterministic `assemble`. So the escalation
cost is:

    B3 ≈ (native miss round) + (1 intent call) + (n_fuzzy_slot narrow calls,
          parallel up to the Phase-0 concurrency ceiling) + (deterministic assemble ~0)

with n_fuzzy_slot = (required slots) − (slots resolved closed-world from the
snapshot). For the canonical hard cases most slots resolve deterministically
(unit/package/path/device/port/interface present in the injected context), so the
dominant escalation term is the single intent call plus at most one or two narrow
slot calls. The concurrency multiplier for those slot calls is exactly the
Phase-0 speedup ratio (CHECKPOINT A) — this is why Phase-0 measured it.

---

## Recovery Steps (run on mossad; fills B1/B2/B3/B4)

Prereq: `ollama list` shows the pinned tier tags; run from the erdtree repo root
on mossad. The audit log is written per-op (I4); point it at a temp path so the
measurement run is self-contained.

```bash
# --- B2: native COMMON-op p50 (baseline) ------------------------------------
# 20 identical common-op turns through the FULL repl under the native default.
ERDTREE_UNDERSTANDING=native ERDTREE_AUDIT_LOG=/tmp/p5-native.jsonl \
  python bench/phase5_latency.py --mode turn --understanding native \
    --request "restart nginx" --n 20 | tee /tmp/p5-b2-native.jsonl

# --- B1: COMMON-op p50 under fast-then-decompose (must EQUAL B2) -------------
ERDTREE_UNDERSTANDING=fast-then-decompose ERDTREE_AUDIT_LOG=/tmp/p5-ftd.jsonl \
  python bench/phase5_latency.py --mode turn --understanding fast-then-decompose \
    --request "restart nginx" --n 20 | tee /tmp/p5-b1-ftd.jsonl

# --- B3: HARD/compound-op p50 under decomposition (escalation cost) ---------
# A phrasing single-shot tends to MISS, so fast-then-decompose escalates.
ERDTREE_UNDERSTANDING=fast-then-decompose ERDTREE_AUDIT_LOG=/tmp/p5-hard.jsonl \
  python bench/phase5_latency.py --mode turn --understanding fast-then-decompose \
    --request "get the box's biggest cpu hog and calm it down a notch" --n 20 \
    | tee /tmp/p5-b3-hard.jsonl
```

If `bench/phase5_latency.py` is not present at run time, the same numbers are
obtainable with the shipped `bench/phase0_harness.py --mode latency` for the raw
single-shot p50 (that is B2), plus timing the repl one-shot directly:

```bash
# raw single-shot p50 (== B2) with the pinned tag from `ollama list`
python bench/phase0_harness.py --mode latency --model <pinned-tag> --n 20

# time the full repl one-shot per understanding mode (median of 20)
for mode in native fast-then-decompose; do
  for i in $(seq 20); do
    /usr/bin/time -f '%e' env ERDTREE_UNDERSTANDING=$mode \
      python core/agent/main.py "restart nginx" >/dev/null 2>>/tmp/p5-$mode.times
  done
done
# p50 = median of /tmp/p5-native.times  vs  /tmp/p5-fast-then-decompose.times
```

Then fill the table and assert **B1 == B2** (within noise; expect ≤1 round-trip
of jitter, since it is literally the same single call). Record **B3** and
**B4 = B3 − B1** as the escalation cost.

---

## GO / NO-GO for flipping the default flag

**Decision: HOLD the default at `native`** until B1/B2/B3 are captured live.

- The correctness/convergence gate (`test_pipeline_convergence.py`) is GREEN — a
  decomposed call cannot reach dispatch except via `permissions.classify` on the
  same synthesized argv, and a destructive decomposed intent gates identically
  (CONFIRM_TYPED / REFUSE). That gate does NOT depend on mossad.
- The latency gate (B1 == B2) is proven by construction + machine-checked on the
  dev host, but Section 9 requires the **live** common-op p50 equality before the
  default flag flips. That single measurement is the only thing outstanding.
- Per keep-stale (invariant #8): `native` stays the shipped default; the pipeline
  ships behind `ERDTREE_UNDERSTANDING=fast-then-decompose` (opt-in) until this
  note is updated with the live B1==B2 confirmation.

---

## Audit Record

```json
{
  "phase": 5,
  "checkpoint": "B",
  "attempted_at": "2026-07-01",
  "mossad_reachable": false,
  "b1_common_op_p50_fast_then_decompose": "== native p50 (by construction; live DEFERRED)",
  "b2_common_op_p50_native": "DEFERRED (mossad offline)",
  "b3_hard_op_p50_decomposition": "DEFERRED (mossad offline)",
  "b4_escalation_delta": "DEFERRED",
  "convergence_gate": "GREEN (test_pipeline_convergence.py, dev-host)",
  "structural_claim_test": "test_fast_path_returns_native_without_touching_decomposition GREEN",
  "default_flag": "HELD at native (keep-stale) pending live B1==B2",
  "verdict": "latency numbers DEFERRED-TO-MOSSAD; correctness gate passed"
}
```
