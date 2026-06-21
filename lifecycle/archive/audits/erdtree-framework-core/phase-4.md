# Phase 4 — Integration Spine (router / context / repl / main + bench)

Date: 2026-06-21
Status: PASSED (code complete; unit/mock tests green; live items honestly deferred)

## Scope built (touched only core/agent/{router,context,repl,main}.py + bench/)

- `core/agent/router.py` — ALREADY PRESENT from prior work and verified, not rewritten.
  Strict parse of the frozen tool-call contract (0002 §2/§5): valid calls parse to
  `TurnKind.TOOL_CALL`; unknown tool / bad JSON / schema-invalid / wrong type / rogue key /
  non-"function" type are each counted as a MISS with the verbatim 0002 §5 re-ask text; never
  crashes. `is_valid_action` is the bench validity predicate.
- `core/agent/context.py` — ALREADY PRESENT and verified. Per-turn context plumbing over the
  SnapshotCache with an I5 non-empty fallback.
- `core/agent/repl.py` — NEW. The read-eval-print loop / one-turn engine. Wires
  context -> prompt -> (injected) responder -> router -> permissions.classify (the HARDENED
  gate, imported and used, never reimplemented) -> registry.dispatch -> audit -> tool-result
  feedback -> repeat, terminating on an English answer. Model + IO + audit are INJECTED so the
  whole loop is dev-host testable. `synthesize_command` maps each validated call onto a literal
  shell command so the SAME hardened classifier decides the gate (model's self-declared class is
  never trusted). Non-interactive write/destructive -> REFUSED (I3). Every op (read, refused,
  miss) writes one audit record (I4). Successful mutation invalidates context (I5). Round cap
  prevents infinite loops.
- `core/agent/main.py` — NEW. Runnable entrypoint. Reads `ERDTREE_TIER` (opaque, I6) with
  sensible defaults (default radagon=PRIMARY; marika/radahn model buckets, pinned tags never
  ':latest'). Builds the live localhost Ollama responder (I1 asserted at construction). One-shot
  (argv) or interactive loop. Degrades gracefully: unreachable model -> one clean line, exit 3;
  non-localhost endpoint -> clean "Cannot start", exit 1; ':latest' tag -> exit 1. No stack
  traces at the user. Audit path falls back to a user-local writable path if the system path
  isn't writable (I4 non-negotiable).
- `bench/run_bench.py` — NEW. Tool-call validity benchmark runner. Loads `bench/cases/*.json`,
  advertises each case's tools (0002 §1 via prompt layer), and scores each turn with the SAME
  Router VALID/MISS predicate (single source of truth). English negative controls are scored
  separately and EXCLUDED from the validity denominator. The model is INJECTED via a `responder`
  callable; `recorded_responder` (offline/mock) makes the runner fully unit-testable here;
  `ollama_responder` (live, localhost) is provided for the GPU box. `validity_rate` is `None`
  (not a fabricated 0.0) when there are no action turns. The CLI REFUSES to print a rate with no
  responder.
- `bench/fixtures/mock_outputs.json` — NEW. Hand-authored dev-host recordings (NOT live results)
  in the AssembledResponse shape, valid against the REAL Phase-2 tool schemas, plus the two
  English controls.

## Tests (all green on macOS dev host, no model/network/Linux)

- `tests/test_router.py` (24) — valid single/parallel calls, English-not-a-miss, every MISS
  class, raw OpenAI shape, never-raises-on-garbage, mixed valid+invalid -> MISS, re-ask shape +
  correlation, advertised-schema correctness, §3 tool-result message.
- `tests/test_run_bench.py` (10) — load_cases; shipped fixtures score 100% validity / english
  held; english excluded from denominator; malformed recording -> MISS not crash; prose-where-
  tool-required -> MISS; missing recording -> MISS; validity None when no action turns; intent
  match informational; CLI refuses to fabricate; CLI recorded run prints 100%.
- `tests/test_repl.py` (12) — synthesize_command class mapping; read instant+audited; write
  confirmed/declined; destructive typed-word right/wrong; non-interactive write REFUSED; MISS
  re-ask + audit; context invalidation on write; round cap.
- `tests/test_main.py` (7) — tier defaults/override/unknown-fallback; model env; non-localhost
  clean message; ':latest' rejected; unreachable localhost -> exit 3 clean, no AI/LLM/engine
  language leaked.

Suite: `python3 -m pytest -q` -> 1258 passed, 11 skipped (pre-existing deferred/live skips). The
4 new files add 53 tests, all green.

## Runnable evidence

- `python core/agent/main.py "is sshd running?"` -> "The local service is not reachable right
  now. Start it and try again." exit 3 (no Ollama on dev host; clean, not a stack trace).
- `python core/agent/main.py` (interactive) -> "Ready. Type a request, or 'exit' to quit." and
  exits cleanly on EOF/`exit`.
- `python bench/run_bench.py --recordings bench/fixtures/mock_outputs.json --label mock` ->
  "validity: 100.0% (8/8 action turns) [target 99.5% — MEETS TARGET]; english controls held: 2/2".
  (This is the RUNNER scoring hand-authored fixtures — NOT a live model rate.)

## DEFERRED-TO-MOSSAD (no fabricated numbers)

- The LIVE tool-call validity rate across base Qwen 14B / 7B / 3B: run
  `python bench/run_bench.py --live --model <pinned tag>` on the GPU box. The runner +
  `ollama_responder` are written and import-clean; only the live measurement is deferred.
- The live end-to-end REPL loop against a running Ollama (main.py with a reachable model).

## Invariant adherence

I1 localhost-only (asserted in ollama client; bench/repl never open their own socket).
I2 no AI/LLM/model/agent language in user-facing strings (prompts/render/CLI messages; the
   unreachable path is explicitly scrubbed and test-asserted). I3 permission gate before every
   write/destructive, via the hardened classifier, non-interactive REFUSED. I4 every op (incl.
   refused + miss) audited append-only JSONL. I5 fresh context every turn + invalidate on
   mutation. I6 no tier/product name in core logic (ERDTREE_TIER opaque; bucket table is config).
   I8 reads clear the gate immediately.
