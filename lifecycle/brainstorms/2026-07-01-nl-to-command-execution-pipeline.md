---
title: Decomposed NL→command execution pipeline (intent → slots → assemble → gate → exec → verify)
date: 2026-07-01
status: brainstorm-only (nothing decided, nothing built)
topic: understanding-pipeline
owner: aaronblatnoy@gmail.com
related:
  - docs/decisions/0002-tool-call-protocol.md (FROZEN — model-native tool calls; this proposal is an alternate understanding strategy beside it)
  - docs/decisions/0003-vector-index.md (sqlite-vec — candidate backend for intent match)
  - core/agent/repl.py (run_turn — the loop this front-half would slot into)
  - core/agent/router.py (the strict validator this replaces on the "understanding" side)
  - core/agent/permissions.py (the hardened gate — MUST be reused, never reimplemented)
  - core/tools/__init__.py (ToolSpec/OpSpec/ArgSpec — the frozen shape "man-page schemas" must produce)
  - bench/run_bench.py (the eval harness this needs for confidence/intent tuning)
  - lifecycle/pending/plans/erdtree-v0.1-buildout.txt, erdtree-p6-p7-p8.txt (what's already built)
---

# Decomposed NL→command execution pipeline

## The idea

Replace the single "the model emits a whole tool call in one shot" step with a
staged pipeline: **[1] intent classifier → [2] parallel per-slot extraction →
[3] deterministic assembler → [4] confirmation surface → [5] direct exec → [6]
verification with bounded retry / tier escalation.** Schemas come from parsed
man pages (versioned for drift), the free-text fallback is demoted and marked,
compound requests get a static plan shown before any step runs, and tiering
routes the smallest capable model first.

The pitch is decomposition-for-reliability: a 3B is bad at "produce a correct,
complete, schema-valid tool call for an arbitrary request in one turn," but much
better at "here is a sentence and ONE narrow question — what is the value?" Cut
the hard problem into many easy ones, and let deterministic code do all the
assembly, validation, and dispatch that a small model does unreliably.

## What it actually replaces (grounding in the current loop)

Today's `repl.run_turn` (core/agent/repl.py) is already the exact spine the spec
describes, just with the understanding collapsed into one model call:

- **Understanding** = one `responder(messages, tools)` call. The model natively
  picks tool + operation + args in a single `tool_calls[]` turn.
- **Validation** = `Router.route()` — strict parse against the per-tool JSON
  schema derived from `ToolSpec`, with salvage heuristics for the many ways a 3B
  mangles a tool call (qwen tags, bare JSON, `name({...})`). A bad turn is a
  MISS → re-ask.
- **Gate** = `synthesize_command(call)` reconstructs a faithful argv string →
  `permissions.classify(argv)` → gate (ALLOW / CONFIRM / CONFIRM_TYPED /
  REFUSE). This is the safety spine and it is deterministic.
- **Exec** = `registry.dispatch` → each tool's `run_subprocess(argv_list)` —
  **already `subprocess.run` with a list argv, already shell-free.**
- **Audit** = one JSONL record per attempted op (including misses/refusals).
- **Re-planning** = the loop feeds tool results back to the model, up to
  `max_rounds` — a *model-driven* re-plan, not a deterministic verify.

So the proposal really touches three things, and it's worth being precise about
which:

| Spec stage | Status in repo today | Real delta |
|---|---|---|
| [1] intent + [2] slots | one native tool-call | **New** — the radical part |
| [3] deterministic assembler | args go model→`_validate_args` (no central default/range logic) | **Mostly new** |
| [4] confirmation surface | exists (`_resolve_gate` + rendered argv) | reuse, re-skin |
| [5] direct fork/exec | `subprocess.run(list)` — **already no shell** | **near-nonexistent delta** |
| [6] verification + retry | model-driven loop only | **New** (the other high-value part) |

**Two honest observations up front.** First, "NEVER produces a shell command
string / fork+exec with no shell parsing" is *a property the codebase already
has* — no tool builds a shell string; `run_subprocess` takes a list and never
uses `shell=True`. Hand-rolling `fork()`/`dup2()`/`pipe()` in Python re-solves a
solved problem and adds a lot of fiddly, safety-sensitive code (fd leaks, SIGCHLD
reaping, signal handling) that `subprocess` already gets right. Don't build it.
Second, the spec's "model must never hold multi-step state" is *already honored*
— the model is stateless per call and all state lives in `run_turn`'s
`messages`/`outcome`. So the durable value of this proposal is concentrated in
**[1]+[2] (decomposed understanding)** and **[6] (deterministic verification)**,
not in re-plumbing execution.

## Design space / options

### A) Replace router/repl in place
Rejected. Violates the "keep stale, build alongside" constraint (#8) and 0002 is
a FROZEN contract. Non-starter.

### B) New isolated module, its OWN execution path (fork/exec bundle)
`core/agent/pipeline/` with intent/slots/assembler/exec/verify, executing bundles
directly. This is the literal reading of the spec. **The danger:** an execution
path that doesn't route through `permissions.classify` reopens every hole
permissions.py closes (the argv-aware destructive taxonomy, default-deny,
non-interactive REFUSE). A second, parallel safety surface *will* drift from the
hardened one. High risk for low incremental benefit.

### C) New understanding module that CONVERGES on the existing spine (recommended)
`core/agent/pipeline/` owns only [1][2][3] (+[6] as read-only post-checks). Its
assembler emits the **same validated `(tool, op, args)` / argv** the current path
produces, then hands off to the EXISTING `_dispatch_calls` → `classify` → gate →
`registry.dispatch` → audit. One integration seam: `run_turn` selects an
"understanding strategy" (default = today's native tool-call router; opt-in = the
decomposed pipeline). Zero edits to permissions.py, router validation, or the
`core/tools` contract. Old tests (which inject a scripted responder) stay green.

**Recommendation: C.** It captures the reliability win of decomposition and the
verification loop while keeping the single hardened gate and the shell-free
executor that already exist. The assembler emitting argv is actually *cleaner*
than today's `synthesize_command`, which has to reverse-engineer argv from
`(tool, op)` — the assembler already holds the argv, so feed it straight to
`classify`.

### The fast-path question (the one that decides whether this is even net-positive)
A decomposed request costs **1 intent call + K slot calls + optional verify
call** where a native tool-call costs **1**. That is a latency regression on the
*common* case ("restart nginx"), and I6 ("simple operations must feel instant")
is a load-bearing invariant, not a nice-to-have.

**Position:** decomposition is an **escalation tier, not the default.** Try the
cheap single-shot native call first; if it returns a clean, schema-valid,
single-tool call, use it (today's behavior, today's latency). Fall into
intent→slots ONLY on a MISS, low confidence, or a detected compound request.
This is exactly the spec's own "smallest appropriate tier first" principle
applied to *pipeline depth*, and it's what reconciles the whole idea with I6.
Further: many slots are extractable **without a model call at all** (unit/package
names, paths, ports via context lookup + narrow regex against the injected system
context). Reserve model slot-workers for genuinely fuzzy slots only.

## Recommendation (summary position)

1. Build the decomposed understanding as an **isolated, opt-in strategy** in
   `core/agent/pipeline/` (option C). It produces validated calls and hands them
   to the **existing** gate/registry/audit spine. Do **not** build a second
   executor; `subprocess.run(list)` is already the shell-free path.
2. Make it an **escalation tier** behind the current single-shot fast path, to
   protect I6. Prove the tradeoff with `bench/` + measured p50 on mossad before
   it ever becomes default.
3. Treat **man-page schemas as a build-time, versioned breadth layer** that
   generates `OpSpec`/`ArgSpec` in the *same* frozen shape, sitting on top of the
   curated 13 tools. Generated tools are **always gated** (default-deny WRITE)
   until a human curates them into the fast path. Curate the top ~50 Radagon
   sysadmin binaries; do not try to parse all of `man`.
4. **Verification = the tool's own read op**, compared to intended state. Retry
   policy keyed on op class: idempotent writes may auto-retry; **destructive /
   non-idempotent ops never auto-retry** — escalate to a human.
5. The free-text fallback still goes **through the gate**, marked and audited
   distinctly, never auto-run.

This is ready to hand to **phase-plan-architect** for the slice: isolated module
+ escalation fast-path + assembler→existing-gate seam + read-op verification. The
man-page parser is a separate, larger track deserving its own plan.

## Man-page schemas vs the frozen ToolSpec

The current `ToolSpec` is a **curated abstraction**: 13 tools, clean ops, each
op's argv hand-mapped in `synthesize_command` so the hardened classifier can rate
it, and READ ops tuned to reach `Gate.ALLOW` so they feel instant. Man-page
schemas are a different animal: thousands of binaries, raw flags, no curated
classifier mapping.

- These are **not competing** — they're two layers. Man-page schemas should
  *generate* `OpSpec`/`ArgSpec` in the exact frozen shape (so router schema
  derivation and `_validate_args` work unchanged), then register as tools.
- A generated tool has **no faithful-argv mapping and no ALLOW tuning**, so it
  lands on the classifier's default-deny floor: WRITE→CONFIRM at best, and
  destructive shapes still escalate via the argv taxonomy. **That is safe** —
  just not fast. Breadth arrives gated; speed arrives only after curation.
- **Parser reality (be candid):** man pages are inconsistent troff/mandoc.
  Edge cases that will bite: flags with optional args (`--color[=WHEN]`),
  mutually exclusive groups, repeatable flags, `--long=val` vs `--long val`,
  positional operands, and subcommands with their *own* man pages
  (git/systemctl/dnf). Aim for **best-effort extraction + human curation of the
  binaries that matter**, not full coverage.
- **Build-time, never runtime.** Parse at build, check in a versioned schema
  artifact. No troff parser on the shipped box (latency, determinism, attack
  surface). Version each schema against the package NEVRA / `--version`; on a
  mismatch at boot, mark that tool **unverified** and force it down the
  gated/fallback path. That's the concrete drift-detection mechanism.

## Verification: what's actually checkable per class

Verification is a strength here *because the registry already has the read ops*:

| Class | Post-check (a READ op) | Auto-retry? |
|---|---|---|
| services | `systemctl is-active/is-failed <unit>` | yes (idempotent) |
| packages install | `rpm -q <pkg>` | yes |
| files write/mkdir | `stat`/`test -e`, checksum | yes |
| firewall | `firewall-cmd --query-service` | yes (reload idempotent) |
| users add | `id <user>` | yes |
| network | `ip addr show <if>` | partial |
| disk format/partition/dd/wipe | `lsblk`/`blkid` | **NO — never auto-retry** |

The spec's flat "bounded retry 2–3 attempts" is dangerous applied uniformly: a
second `mkfs`/`dd`/`userdel` is catastrophic or meaningless. **Retry must be
gated on op class**, and destructive failures escalate to a human, full stop.

## Tier escalation — the honest limit

Ollama is tier-agnostic (`TierConfig` injected), so escalating Marika→Radagon is
mechanically clean. But **Marika (3B) and Radagon (7–14B) are different
products/distros** — a Marika box likely does not have Radagon weights installed,
and on 2×3060 Ti (8GB) a 3B and a 14B won't happily co-reside; a model swap is a
cold-load latency hit. So the realistic ladders differ:

- **Marika:** single-shot → decomposed pipeline → ask the human. (No bigger
  model to escalate to.)
- **Radagon-class hardware:** single-shot → decomposed → larger-model retry.

Don't over-promise cross-tier model escalation as a universal rung.

## Risks & safety (highest-stakes first)

- **R1 — a second execution path that bypasses `classify`.** The single biggest
  risk. Any exec that doesn't feed argv through permissions.py reopens the whole
  destructive taxonomy. *Mitigation: option C — converge on the existing gate;
  never build a parallel executor.*
- **R2 — free-text fallback = unbounded command generation.** Today there is NO
  free-text→shell path (non-tool-call output is a MISS or plain English). Adding
  one is a new danger surface. *Mitigation: fallback argv still goes through
  `classify` + gate, is visually marked "unverified / best-effort," is audited
  with a distinct flag, and is never auto-run.*
- **R3 — auto-retry of destructive/non-idempotent ops.** *Mitigation: retry
  keyed on op class; destructive → escalate, never repeat.*
- **R4 — latency regression breaks the illusion (I6).** N model calls where 1
  did. *Mitigation: decomposition as escalation tier; deterministic slot
  extraction first; measure p50 before defaulting.*
- **R5 — man-page schema drift** (schema says a flag means X; installed binary
  changed it). *Mitigation: version pin + drift → unverified → gated/fallback.*
- **R6 — uncalibrated 3B confidence.** Thresholds will over- or under-escalate.
  *Mitigation: tune on `bench/` with a labeled set; treat confidence as a coarse
  signal, not a precise dial.*
- **I2 / I1 hygiene:** the plan/confirmation/verification surfaces must stay free
  of "AI/model/LLM" language (they already speak Linux), and every extra
  inference call is still localhost Ollama — N calls means N× local compute, not
  new egress.

## Dependencies & sequencing

1. **Measure first.** Current p50 of a single 3B tool-call on mossad, and whether
   Ollama on the 2-GPU box *actually* decodes slot workers concurrently or
   serializes them (`OLLAMA_NUM_PARALLEL`). Without these numbers the whole
   latency argument is speculation. **This gates the go/no-go.**
2. **Bench harness** (`bench/run_bench.py`, cases/, fixtures/) extended with a
   labeled intent+slot set — needed to tune confidence and prove decomposition
   beats single-shot on hard cases without wrecking easy ones.
3. **A 0004 decision doc** situating the new understanding strategy beside the
   frozen 0002, so the two coexist explicitly.
4. **Man-page parser** — a separate, larger build-time track. Not on the critical
   path for the escalation-strategy slice.
5. Optional: **0003 sqlite-vec index** could power intent match via
   schema-description similarity (a retrieval, not a generation call) — cheaper
   and more deterministic than a model classifier. Worth a spike.

## Open questions

- Is **intent** best done as a model call, or as embedding similarity over schema
  descriptions using the existing sqlite-vec index (0003)? The latter avoids a
  generation round-trip — needs a spike.
- Does the OpenAI-compat Ollama endpoint expose **logprobs / a usable confidence
  signal**? If not, "confidence" must be synthesized (e.g. self-consistency
  across slot samples), which costs *more* calls. Unverified — do not assume.
- What is the measured **single-shot p50** today, and the **real concurrency**
  of slot workers on 2×3060 Ti? (See dependency 1.)
- How many binaries does **Radagon actually need day-one**? Curate a top-N list
  rather than boiling the man-page ocean.
- On **Marika hardware**, is a larger model ever present to escalate to, or is the
  top rung always "ask the human"? (Likely product-defining.)
- Where do **defaults / ranges** live — in the assembler, or per-`ArgSpec`
  (`ArgSpec.default` exists but is not centrally applied today)? The assembler is
  the natural home, but that's a small extension to the frozen contract's usage.

## Status
brainstorm only — nothing built or decided.
