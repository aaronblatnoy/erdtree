# Phase-0 Measurements — NL Pipeline Buildout

**Date attempted:** 2026-07-01  
**Executor:** Claude Sonnet 4.6 (subagent, single context)  
**Target host:** mossad (aaron@192.168.1.163 / Tailscale 100.94.62.115)

---

## Status: INFRASTRUCTURE UNAVAILABLE

mossad was **offline** at measurement time.

Tailscale status confirmed: `offline, last seen 1d ago, tx 4992 rx 0`

Both network paths timed out:
- `ssh aaron@192.168.1.163` — Operation timed out (LAN)
- `ssh mossad` (Tailscale 100.94.62.115) — Operation timed out

No live Ollama endpoint was reachable.  Per the bench/run_bench.py honesty gate
and plan invariant I1, this harness does NOT fabricate numbers.

---

## What Was Prepared

A measurement harness was written and committed at `bench/phase0_harness.py`.
It covers all three Phase-0 measurements:

### Measurement 1 — Single-shot p50/p95 (latency mode)

```
python bench/phase0_harness.py --mode latency \
  --model <pinned-3b-tag> --n 20

python bench/phase0_harness.py --mode latency \
  --model <pinned-14b-tag> --n 20
```

Records wall-clock per turn over N=20 identical tool-call turns.
Emits JSON lines; summary includes p50_s, p95_s, mean_s, min_s, max_s.

### Measurement 2 — Slot-worker concurrency (concurrency mode)

```
for NP in 1 2 4; do
  for K in 3 5; do
    OLLAMA_NUM_PARALLEL=$NP python bench/phase0_harness.py \
      --mode concurrency --model <pinned-3b-tag> --k $K --repeats 3
  done
done
```

For each (NUM_PARALLEL, K) cell: measures serial vs parallel wall-clock for K
narrow single-slot calls.  Reports speedup_ratio and whether it exceeds the 1.3x
GO criterion.  The narrow calls use a minimal text prompt (no tool schema) to
isolate decode throughput from schema overhead.

### Measurement 3 — Logprob presence (logprobs mode)

```
python bench/phase0_harness.py --mode logprobs \
  --model <pinned-3b-tag>
```

Sends `logprobs=true, top_logprobs=1` to `/v1/chat/completions` and inspects
whether the response carries a `logprobs` field in the choices.  Ollama >= 0.3.6
added partial logprob support; availability is model-dependent.

---

## Concrete Numbers

| Measurement | Value |
|-------------|-------|
| Single-shot p50, 3B tier | **NOT MEASURED** (mossad offline) |
| Single-shot p95, 3B tier | **NOT MEASURED** |
| Single-shot p50, 14B tier | **NOT MEASURED** |
| Single-shot p95, 14B tier | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=1, K=3 | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=2, K=3 | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=4, K=3 | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=1, K=5 | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=2, K=5 | **NOT MEASURED** |
| Speedup at NUM_PARALLEL=4, K=5 | **NOT MEASURED** |
| Logprobs available | **NOT MEASURED** |

---

## GO / NO-GO Verdict

**NO-GO.**

GO criterion (from plan Phase 0):
> Parallel slot workers achieve >1.3x speedup at some NUM_PARALLEL AND
> single-shot p50 is known (so the escalation budget is real).

Single-shot p50 is **not known**.  The first conjunct of the GO criterion is
unmet regardless of what the speedup might be.

This is a measurement-gap NO-GO, not an architectural NO-GO.  The plan's
NO-GO recovery path applies:

> if slot workers strictly serialize with no speedup, still record numbers
> (decomposition survives serial as a slow escalation tier — the USER decides).

Because numbers are absent rather than bad, **the user must decide**:
- Bring mossad online and re-run this phase (recommended; unblocks Phase 1).
- Or proceed with Phase 1 (the pure spine refactor, no live model needed) while
  Phase 0 runs in parallel once mossad is available.

---

## Recovery Steps

1. Bring mossad online.
2. Confirm `ollama list` shows the tier model tags.
3. From the erdtree repo root on mossad:

```bash
# Latency — 3B tier (replace tag with actual pinned tag from `ollama list`)
python bench/phase0_harness.py --mode latency \
  --model qwen2.5:3b-instruct-q4_K_M --n 20 \
  | tee /tmp/phase0-latency-3b.jsonl

# Latency — 14B tier
python bench/phase0_harness.py --mode latency \
  --model qwen2.5:14b-instruct-q4_K_M --n 20 \
  | tee /tmp/phase0-latency-14b.jsonl

# Concurrency sweep
for NP in 1 2 4; do
  for K in 3 5; do
    OLLAMA_NUM_PARALLEL=$NP \
    python bench/phase0_harness.py --mode concurrency \
      --model qwen2.5:3b-instruct-q4_K_M --k $K --repeats 3 \
      | tee -a /tmp/phase0-concurrency.jsonl
  done
done

# Logprobs
python bench/phase0_harness.py --mode logprobs \
  --model qwen2.5:3b-instruct-q4_K_M \
  | tee /tmp/phase0-logprobs.jsonl
```

4. Copy results back to the dev host and fill in the table above:

```bash
scp mossad:/tmp/phase0-*.jsonl runtime/audits/nl-pipeline/
```

5. Update this file with the concrete numbers.
6. Re-evaluate the GO/NO-GO verdict.
7. If GO: proceed with Phase 1.
   If NO-GO (serializes, no speedup): update docs/decisions/0004 with the
   confirmed serial posture and proceed (decomposition is still viable as a slow
   escalation tier; the user decides whether to build it).

---

## Architectural Notes (not blocked by mossad)

The following conclusions from the plan hold regardless of the measurements
and are recorded in docs/decisions/0004-understanding-strategy.md:

- **Option C (converge on the spine)** is the selected approach.  Options A
  (replace router) and B (second executor) are rejected.
- The escalation-tier posture means decomposition never fires on the fast path,
  so the common-op p50 is structurally invariant regardless of what the
  decomposition latency turns out to be.
- If the concurrency measurement shows serialization (speedup ≈ 1.0 at all
  NUM_PARALLEL values), Phase 4 must prefer deterministic slot extraction and
  cap model slot-workers to 1 or 2.  The reliability win from decomposition
  (turning a hard one-shot into many easy ones) survives serial execution;
  only the escalation cost is higher.
- If logprobs are absent, confidence is synthesized from intent-distance +
  required-slot completeness + assembler-validation success (Assumption A2 in
  the plan).  Self-consistency sampling is the fallback but costs more calls.

---

## Audit Record

```json
{
  "phase": 0,
  "attempted_at": "2026-07-01",
  "mossad_reachable": false,
  "tailscale_status": "offline, last seen 1d ago",
  "measurements_taken": [],
  "harness_written": "bench/phase0_harness.py",
  "verdict": "NO-GO",
  "reason": "single-shot p50 not known (mossad offline)",
  "recovery": "bring mossad online, re-run harness, update this file"
}
```
