// Erdtree — Harness UX Upgrade: Streaming, Live Tool Steps, Small-Model Prompt
// Discipline, Tighter Self-Correction. Makes Erdtree's OWN harness (core/agent/)
// FEEL like Claude Code / OpenCode — token-by-token streaming, live "running:
// <cmd>" tool steps, a 7B/3B-tuned tool-use prompt, and a tighter self-correcting
// re-ask — WITHOUT touching the permission gate, audit spine, or dead-man
// fallback, and WITHOUT any new egress. This compiles the ENTIRE plan
// (P0-P6) at lifecycle/pending/plans/erdtree-harness-ux.txt, so it archives the
// plan on full success.
//
// EXECUTION SHAPE (plan §3, §12.1 DAG):
//        P0 ──> P1 ──> P2 ──> P3 ──┐
//                                  ├──> P6 (integration wiring + invariance gate)
//        P4 ───────────────────────┤   (P6 wiring = opus agent; SC4 safety gate
//        P5 ───────────────────────┘    = audit-duo WORKFLOW)
//
// THE STREAMING SPINE (P1->P2->P3) is a coupled chain through the two SINGLE-WRITER
// files and MUST be serial: ollama.py is edited ONLY in P1; repl.py is edited in P2
// AND P3 — P2 then P3 strictly serial, NEVER parallel-edit repl.py. P4 (prompt.py)
// and P5 (router.py) touch DISJOINT files from the spine and from each other ->
// the ONLY genuinely-parallel pair; they are dispatched in the BACKGROUND at the
// start, concurrent with the P0->P3 chain, and harvested at the P6 join.
//
// SC4 IS THE LOAD-BEARING SAFETY CLAIM: streaming is PRESENTATION ONLY. The loop
// still assembles a full AssembledResponse BEFORE routing/gating/dispatch; a
// streamed token NEVER represents an unconfirmed write; gate/audit/dead-man are
// BYTE-BEHAVIOR-UNCHANGED. P6's invariance proof re-runs the P0 "before" oracle
// against the fully-wired streaming path and asserts gate/audit/TurnOutcome are
// IDENTICAL. That irreversible-feeling join routes to the audit-duo WORKFLOW
// (genuinely-independent adversarial confirmation) — NOT the
// consensus-verification-duo agentType (which nests + collapses to one
// self-arguing context = theater, the exact failure this designer exists to avoid).
//
// MODEL AVAILABILITY NOTE (from the dispatch brief): sonnet had an outage earlier
// this session. The P6 audit-duo reviewers are pinned to OPUS (model:'opus' in the
// workflow args), and a null/errored/529 reviewer is treated as UNRESOLVED -> the
// workflow ESCALATES (never a silent pass on the SC4 safety gate). P4/P5 keep the
// plan's sonnet assignment (prose/string work, deterministic tests, retry-safe);
// if sonnet errors they simply fail their pass gate and the spine reports the gap.
//
// HOST REALITY: this build host is LINUX (Arch). pytest IS in the project venv at
// /home/aaron/erdtree/.venv/bin/python -m pytest (NOT system python3) — every agent
// is told this explicitly. The whole plan is unit-provable on this host with
// scripted/chunked-responder doubles; the ONLY honestly-deferred item is the live
// 7B/14B Ollama round-trip FEEL (needs a provisioned Linux box + Ollama running a
// real model) -> DEFERRED-TO-MOSSAD, recorded, never faked.

export const meta = {
  name: 'erdtree-harness-ux',
  description: 'Compile the Erdtree Harness UX Upgrade (P0-P6): make the OWN harness (core/agent/) feel like Claude Code/OpenCode. P0 pins a frozen gate/audit/render "before" oracle. The STREAMING SPINE P1->P2->P3 is a strict serial chain through the two single-writer files: P1 adds an ADDITIVE streaming responder to core/model/ollama.py (drain stream(), emit content tokens via an on_delta sink, return the SAME AssembledResponse chat() would); P2 extends ReplIO with OPTIONAL render_delta/tool_step/tool_step_result + ConsoleIO impls + stream-drain wiring, guarding against double-rendering the final English answer; P3 emits I2-clean live "running: <synth cmd>" + result lines in _dispatch_calls ONLY after the gate clears. P4 (prompt.py: small-model tool-use discipline + few-shot) and P5 (router.py: tighter instructive re-ask within the frozen TurnKind/role:"tool" shape) are the only genuinely-parallel pair — dispatched in the background concurrent with the spine, harvested at P6. P6 wires the streaming responder into main.py build_repl (buffered path kept reachable), verifies the shell dead-man guard (I9), and PROVES SC4 by re-running the P0 oracle against the streaming path. HARD INVARIANTS threaded through every phase: I1 localhost-Ollama-only (reuse the loopback-asserted client, no new socket), I2 every NEW user-facing string passes _FORBIDDEN_AI_TERMS, gate/audit/dead-man BYTE-UNCHANGED (streaming is presentation only; a streamed token never implies an unconfirmed write ran), backward-compatible (buffered responder + ConsoleIO stay default so the >=1795-test suite stays green; streaming is additive + injectable with a scripted-chunked-responder double). The SC4 invariance gate routes to the audit-duo WORKFLOW (opus reviewers; null/529 => UNRESOLVED => escalate), never the consensus-verification-duo agentType. Tests run via .venv/bin/python -m pytest. Archives the plan on full success.',
  phases: [
    { title: 'P0: Pin the invariance baseline (frozen before-oracle)', detail: 'Characterization test over a fixed set of scripted turns (read / confirmed write / declined write / destructive wrong-word / MISS+re-ask) through Repl.run_turn with the EXISTING buffered ScriptedResponder + FakeIO, freezing audit count + permission_decision strings + FakeIO.rendered + TurnOutcome fields. The frozen "before" oracle for SC4. sonnet.' },
    { title: 'P1: Streaming responder adapter (ollama.py, additive)', detail: 'ADDITIVE streaming responder draining stream() and emitting content tokens via an on_delta sink, returning the SAME AssembledResponse chat() assembles (parity); reuse chat()\'s tool-call accumulation (no fork); reuse the SAME loopback-asserted OllamaClient (I1, no new socket); on_delta wrapped so it never aborts assembly. chat() byte-behavior-unchanged. opus. SINGLE-WRITER ollama.py.' },
    { title: 'P2: ReplIO incremental hook + stream drain in run_turn (repl.py)', detail: 'Extend ReplIO with OPTIONAL render_delta/tool_step/tool_step_result (feature-detected; render()-only IOs still work). ConsoleIO.render_delta = live token write+flush, I2-clean. Wire the responder\'s on_delta -> io.render_delta WITHOUT changing the buffered path; guard against DOUBLE-rendering the final English answer; degrade if render_delta raises. FakeIO gains delta capture (SC1). opus. SINGLE-WRITER repl.py (serial with P3).' },
    { title: 'P3: Live tool-call display in _dispatch_calls (repl.py)', detail: 'Emit io.tool_step("running: " + synthesize_command(call)) ONLY after the gate clears (never imply an unconfirmed write ran; declined ops get a "not run" status, never "running"), and a terse I2-clean tool_step_result after dispatch derived from ToolResult. Do NOT add/move any audit.write or touch gate logic (SC4 audit-count parity). opus. SINGLE-WRITER repl.py (after P2).' },
    { title: 'P4: Small-model tool-use discipline + few-shot (prompt.py)', detail: 'TIGHT tool-use discipline block + 2-3 small-model few-shot examples appended to the house system prompt, all I2-clean (import-time _assert_no_ai_language must pass; few-shot must avoid "the assistant will..." phrasing) and matching the 0002 wire shape (each tool-call example passes router.validate_arguments with no MISS). sonnet. PARALLEL with P5 + the spine; background.' },
    { title: 'P5: Tighter, more instructive self-correcting re-ask (router.py)', detail: 'Sharpen the three re-ask strings (reask_invalid_arguments/reask_unknown_tool/reask_invalid_input) to echo the exact validator detail / valid-operation enum / offending token, WITHOUT changing TurnKind, is_valid_action, or the role:"tool" re-ask SHAPE, and keep them I2-clean. sonnet. PARALLEL with P4 + the spine; background.' },
    { title: 'P6: Integration wiring + invariance gate + full-suite green', detail: 'Wire the streaming responder into build_repl (main.py) with on_delta -> ConsoleIO.render_delta, keep the buffered path reachable; verify the shell dead-man guard still wraps the streaming turn (I9); run the FULL suite green (>=1795 + new); PROVE SC4 by re-running the P0 oracle against the streaming path (gate/audit/TurnOutcome identical); consolidated I2 inventory of every new string. The SC4 safety claim is confirmed by the audit-duo WORKFLOW (opus reviewers). opus wiring.' },
    { title: 'F: Archive plan on success', detail: 'Only when EVERY phase passed: record the rollup and move the plan pending -> archive (this workflow executes the ENTIRE P0-P6 plan).' },
  ],
};

const REPO = '/home/aaron/erdtree';
const PLAN = REPO + '/lifecycle/pending/plans/erdtree-harness-ux.txt';
const PLAN_ARCHIVE = REPO + '/lifecycle/archive/plans/erdtree-harness-ux.txt';
const CLAUDE_MD = REPO + '/CLAUDE.md';
const AUDIT_DIR = REPO + '/runtime/audits/erdtree-harness-ux';
const PYTEST = '.venv/bin/python -m pytest';

// Build agents return a structured pass the JS branches on (no model does control flow).
const passSchema = {
  type: 'object',
  required: ['passed', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    testsRun: { type: 'string', description: 'the exact .venv/bin/python -m pytest command(s) run and a one-line pass/fail tally per command' },
    newStrings: { type: 'array', items: { type: 'string' }, description: 'every NEW user-facing string introduced (progress/tool-step/re-ask), for the P6 consolidated I2 inventory' },
    deferred: { type: 'array', items: { type: 'string' }, description: 'only genuinely environment-blocked items (the live 7B/14B Ollama round-trip FEEL -> DEFERRED-TO-MOSSAD), with the reason' },
    summary: { type: 'string' },
  },
};

// Audit-duo returns a verdict the JS branches on. null/errored reviewer => UNRESOLVED.
const duoSchema = {
  type: 'object',
  required: ['verdict', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNRESOLVED'] },
    findings: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

// Shared invariant + host block threaded into EVERY agent brief.
function preamble(phaseId) {
  return (
    `IMPORTANT — REPO ROOT: the Erdtree repo is at ${REPO}. Your shell CWD may be elsewhere, so FIRST run ` +
    `cd ${REPO}, and treat EVERY relative path below as relative to that repo root (e.g. "core/agent/repl.py" means ` +
    `${REPO}/core/agent/repl.py). Before anything: read ${CLAUDE_MD} (canonical context + Load-Bearing Invariants) and ` +
    `the relevant §3 phase section of ${PLAN}.\n\n` +
    `WHAT EXISTS (completed + verified — import/use, do NOT rewrite): the whole P0-P11 v0.1 agent loop. Key seams for THIS ` +
    `plan, with VERIFIED line numbers (read them, do not reinvent):\n` +
    `  - core/model/ollama.py: _assert_localhost (:47), AssembledResponse (:132), OllamaClient (:235, asserts localhost at ` +
    `:254), stream() (:263, yields StreamChunk content_delta + tool-call deltas), chat() (:296, joins content_parts at :307 ` +
    `and accumulates tool-call deltas :307-339, returns AssembledResponse :341). The stream ALREADY exists — chat() collapses ` +
    `it in OUR code; that is the spine fix.\n` +
    `  - core/agent/repl.py: ReplIO Protocol (:65 — render/confirm/confirm_typed), ConsoleIO (:73), synthesize_command (:137, ` +
    `produces I2-clean shell argv), run_turn (:457), _dispatch_calls (:574), _resolve_gate (:635), _safe_dispatch (:672).\n` +
    `  - core/agent/prompt.py: _FORBIDDEN_AI_TERMS (:44), _AI_PATTERN (:58), _assert_no_ai_language (:64, fails the build at ` +
    `import if a forbidden term appears), _HOUSE_SYSTEM_PROMPT (:85, import-time asserted at :113), build_tool_list (:149), ` +
    `assemble_messages (:177, system_parts at :192).\n` +
    `  - core/agent/router.py: reask_invalid_arguments (:58), reask_unknown_tool (:66), reask_invalid_input (:71), TurnKind ` +
    `(:80), is_valid_action (:128), validate_arguments (:255 — already computes precise detail strings).\n` +
    `  - core/agent/main.py: build_repl (:166); the buffered closure returns client.chat(...) at :181.\n` +
    `  - shell/shell.py: the login shell with the OUTERMOST dead-man bash fallback (I9); raises/handles ConnectionError mid-turn.\n` +
    `  Existing tests to keep green: tests/test_repl.py (ScriptedResponder, FakeIO, _make_repl, _stub_tool_results), ` +
    `tests/test_router.py, tests/test_ollama_roundtrip.py (the _http_factory injection pattern), tests/test_main.py, ` +
    `tests/test_deadman.py. The full suite is >=1795 tests.\n\n` +
    `HARD INVARIANTS — thread through every change, prove with a test:\n` +
    `  I1  Streaming talks ONLY to localhost Ollama. REUSE the existing loopback-asserted OllamaClient (stream() already ` +
    `      asserts localhost at construction). Open NO new socket, name NO new host.\n` +
    `  I2  EVERY NEW user-facing string (progress lines, "running:" display, re-ask wording, few-shot prose) must pass the I2 ` +
    `      filter: import _AI_PATTERN / _assert_no_ai_language from core.agent.prompt (do NOT re-list the terms) — no ` +
    `      ai/llm/model/agent/agentic/inference/ollama. Prompt strings ALSO fail the build at import via ` +
    `      _assert_no_ai_language. Speak plain command-interface language ("running: <cmd>", "done", "exit 0", "not run"), ` +
    `      never "the assistant/agent will...".\n` +
    `  SC4 GATE/AUDIT/DEAD-MAN BYTE-BEHAVIOR-UNCHANGED. Streaming is PRESENTATION ONLY: the loop still assembles a full ` +
    `      AssembledResponse-equivalent BEFORE routing/gating/dispatch (A3); the router/gate/audit see the SAME assembled turn ` +
    `      they see today. A streamed token is content ONLY and NEVER represents an unconfirmed write. Do NOT add, move, or ` +
    `      remove any audit.write; do NOT touch permissions.classify or the gate ordering. Tool-step display is NOT an audit ` +
    `      substitute (I4 unchanged).\n` +
    `  BACK-COMPAT The buffered responder + ConsoleIO path stays the DEFAULT so the existing suite stays green. Streaming is ` +
    `      ADDITIVE + INJECTABLE — provide/use a scripted CHUNKED-responder double; absence of a streaming responder/IO ` +
    `      degrades to today's render(text) behavior.\n` +
    `  I9  Dead-man fallback (shell/shell.py) byte-untouched; introduce NO new unbounded wait and never swallow ConnectionError.\n\n` +
    `HOST REALITY: this build host is LINUX (Arch). pytest IS available in the PROJECT VENV — run tests with ` +
    `"${PYTEST}" (NOT system python3). The plan is unit-provable here with scripted/chunked-responder doubles; actually run ` +
    `the tests and paste the real pass lines — NEVER fabricate a tally. The ONLY legitimately deferred item is the LIVE ` +
    `7B/14B Ollama round-trip FEEL (needs a provisioned box + Ollama running a real model) -> record it as DEFERRED-TO-MOSSAD ` +
    `with the reason; do NOT claim a live round-trip.\n\n` +
    `Write evidence to ${AUDIT_DIR}/phase-${phaseId}.md (create the dir if needed). Print a one-line summary and exit.\n\n`
  );
}

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log('Erdtree Harness UX Upgrade (P0-P6) starting: streaming spine + live tool steps + prompt discipline + tighter re-ask, SC4-gated.');

// ===================================================================
// P4 + P5 — the ONLY genuinely-parallel pair. Disjoint files (prompt.py,
// router.py) from the spine and from each other. Dispatch in the BACKGROUND
// at the very start so they run CONCURRENT with the P0->P3 chain; harvest at P6.
// (Promises started now; awaited at the join.)
// ===================================================================
phase('P4: Small-model tool-use discipline + few-shot (prompt.py)');
const p4Promise = agent(
  preamble('4') +
    `Execute Phase 4 (PROMPT DISCIPLINE — independent of the streaming spine; you are running in PARALLEL with it).\n` +
    `Your slice, touching ONLY core/agent/prompt.py and tests/test_prompt_fewshot.py:\n` +
    `1. Append a TIGHT TOOL-USE DISCIPLINE block to the house system prompt (new constant assembled into the system message ` +
    `in assemble_messages :177, OR appended to _HOUSE_SYSTEM_PROMPT :85): "call a system operation when the request needs ` +
    `one or needs a fact; answer directly when it is a plain question; never narrate that you are about to do something; be ` +
    `terse; one operation at a time when unsure." KEEP IT SHORT — small models (3B/7B) drown in long prompts; mirror Claude ` +
    `Code/OpenCode terseness.\n` +
    `2. Add a SHORT FEW-SHOT (2-3 examples, prefer 2): one request -> a single clean tool call (correct operation enum + ` +
    `args in the EXACT 0002 wire shape the router expects), and one request -> a direct English answer with NO tool call. ` +
    `Derive the example args from a real registry ToolSpec shape (e.g. a services.status read).\n` +
    `3. I2 IS THE TRICKY SURFACE HERE: every new constant must pass _assert_no_ai_language at import (the file already does ` +
    `this for _HOUSE_SYSTEM_PROMPT). The few-shot must describe operations WITHOUT forbidden words — say "the systemctl ` +
    `operation" / "the dnf operation", never "the assistant/agent/model will...". Keep the just-added English-only rule ` +
    `intact and ordered.\n` +
    `4. WRITE tests/test_prompt_fewshot.py: SC6 — the assembled system message CONTAINS the discipline block + at least one ` +
    `tool-call few-shot + one direct-answer few-shot; SC3 — the WHOLE assembled prompt passes _assert_no_ai_language; a ` +
    `WIRE-SHAPE PARITY test — parse each tool-call example and run it through router.validate_arguments against the matching ` +
    `ToolSpec and assert NO MISS (a drifted example would teach the wrong format). Keep assemble()/assemble_messages ` +
    `signatures unchanged; existing test_prompt / snapshot tests green.\n` +
    `5. Run "${PYTEST} tests/test_prompt_fewshot.py -q" and "${PYTEST} tests/test_snapshot.py -q" (and any existing prompt ` +
    `test) and paste the real pass lines into testsRun. Populate newStrings with every user-facing string you added (the ` +
    `discipline block + few-shot text) so P6 can re-inventory them. passed=true REQUIRES SC6 + SC3 + the wire-shape parity ` +
    `test green and the import-time _assert_no_ai_language passing.`,
  { label: 'P4-prompt-discipline', phase: 'P4: Small-model tool-use discipline + few-shot (prompt.py)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema, run_in_background: true }
);

phase('P5: Tighter, more instructive self-correcting re-ask (router.py)');
const p5Promise = agent(
  preamble('5') +
    `Execute Phase 5 (RE-ASK TIGHTENING — independent; you are running in PARALLEL with the spine and P4).\n` +
    `Your slice, touching ONLY core/agent/router.py and tests/test_router.py:\n` +
    `1. Make the three re-ask strings more INSTRUCTIVE so a small model can self-correct: reask_invalid_arguments (:58) ` +
    `echoes the EXACT validator detail (validate_arguments :255 already yields precise messages like "'operation' must be ` +
    `one of [install, remove, ...], got 'instal'"); reask_unknown_tool (:66) names the offending tool and may list valid ` +
    `tool names; reask_invalid_input (:71) surfaces the offending token. Thread the concrete fix through — lead with it, keep ` +
    `each message to one or two sentences (over-verbose re-asks confuse small models).\n` +
    `2. FROZEN CONTRACT — do NOT change: TurnKind classification (:80), is_valid_action (:128, the MISS/VALID predicate), or ` +
    `the reask_messages role:"tool" + tool_call_id SHAPE (per 0002 §5). The loop's re-ask path and bench scoring depend on ` +
    `them. You are changing WORDING ONLY.\n` +
    `3. Every re-ask string must pass the I2 filter (import _AI_PATTERN from core.agent.prompt) — speak about "the <tool> ` +
    `tool" and "the input", never model/agent words.\n` +
    `4. tests/test_router.py: keep all existing tests green (classification unchanged); ADD asserts that a malformed call ` +
    `(bad operation enum) produces a re-ask string CONTAINING the valid-operations list, an unknown tool produces one naming ` +
    `the offending tool, and BOTH pass _AI_PATTERN.\n` +
    `5. Run "${PYTEST} tests/test_router.py -q" and paste the real pass line into testsRun. Populate newStrings with the new ` +
    `re-ask wording (include a before/after for at least one) so P6 can re-inventory them. passed=true REQUIRES test_router.py ` +
    `green with the new asserts AND the frozen TurnKind/shape untouched.`,
  { label: 'P5-reask-tightening', phase: 'P5: Tighter, more instructive self-correcting re-ask (router.py)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema, run_in_background: true }
);

// ===================================================================
// P0 — Pin the invariance baseline. Frozen "before" oracle for SC4.
// sonnet (characterization over an understood surface). Gates the spine.
// ===================================================================
phase('P0: Pin the invariance baseline (frozen before-oracle)');
const p0 = await agent(
  preamble('0') +
    `Execute Phase 0 (PIN THE INVARIANCE BASELINE). Your slice, touching ONLY tests/test_invariance_baseline.py:\n` +
    `1. REUSE the fixtures already in tests/test_repl.py (ScriptedResponder, FakeIO, _make_repl, _stub_tool_results) — do ` +
    `NOT re-invent them.\n` +
    `2. Run a FIXED set of scripted turns through Repl.run_turn with the EXISTING buffered ScriptedResponder + FakeIO: one ` +
    `read, one CONFIRMED write, one DECLINED write, one DESTRUCTIVE wrong-word, one MISS+re-ask. Record and ASSERT ` +
    `EXPLICITLY: the exact audit record COUNT + the permission_decision strings; the FakeIO.rendered list (what render() ` +
    `received) for the ENGLISH answers ONLY (do NOT over-pin — tool-step lines added in P3 go through NEW hooks, not ` +
    `render(), so pinning render() exact strings for non-English would make legitimate P3 additions noisy); and the ` +
    `TurnOutcome fields (tool_calls_made, refused, misses, rounds).\n` +
    `3. These become the FROZEN "before" oracle: structure the test so any later phase that perturbs gate/audit/render ` +
    `breaks THIS test loudly, and so P6 can IMPORT/RE-RUN it unchanged against the streaming path.\n` +
    `4. Run "${PYTEST} tests/test_invariance_baseline.py -q" and paste the real pass line into testsRun; paste the asserted ` +
    `baseline NUMBERS (audit count, decision strings, outcome fields) into the evidence file. passed=true REQUIRES the test ` +
    `green with concrete asserted numbers matching CURRENT behavior.`,
  { label: 'P0-baseline-oracle', phase: 'P0: Pin the invariance baseline (frozen before-oracle)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (p0.passed !== true) {
  return { status: 'HALTED_AT_P0', reason: 'baseline oracle not pinned green; the SC4 invariance proof at P6 has no "before" to compare against. Leaving the plan in pending/.', p0 };
}

// ===================================================================
// STREAMING SPINE — P1 -> P2 -> P3, STRICT SERIAL. ollama.py single-writer (P1);
// repl.py single-writer (P2 then P3). opus throughout (transport/loop-spine
// surgery adjacent to the gate/audit; SC4 rides on it).
// ===================================================================
phase('P1: Streaming responder adapter (ollama.py, additive)');
const p1 = await agent(
  preamble('1') +
    `Execute Phase 1 (STREAMING RESPONDER ADAPTER). Your slice, touching ONLY core/model/ollama.py and a streaming test ` +
    `double in tests/test_streaming.py:\n` +
    `1. Add an ADDITIVE streaming responder: a callable (messages, tools) -> AssembledResponse that internally drains ` +
    `client.stream(...) and, for each chunk.content_delta, calls an injected on_delta(token) sink BEFORE returning. Net ` +
    `effect: an AssembledResponse IDENTICAL to what chat() would assemble from the same chunks, PLUS a side-channel of ` +
    `content tokens.\n` +
    `2. SHARE the tool-call delta accumulation with chat() (:307-339) — factor it into a small reusable helper OR have the ` +
    `streaming responder call into the same accumulation. Do NOT FORK it (a fork risks chat()/stream divergence -> a tool ` +
    `call assembled differently in the two paths). chat() MUST remain byte-behavior-identical (test_ollama_roundtrip.py stays ` +
    `green).\n` +
    `3. I1: the streaming responder takes the OllamaClient + an on_delta sink; it does NOT open its own socket — it calls ` +
    `client.stream(), which already asserts localhost at construction. No new socket, no new host.\n` +
    `4. on_delta must NEVER raise into the loop: WRAP the sink call so a rendering error degrades to no-stream and never ` +
    `aborts assembly.\n` +
    `5. Provide a factory the loop/main can wire (stream via on_delta into the IO's incremental hook, introduced P2).\n` +
    `6. TEST DOUBLE: in tests/test_streaming.py add a streaming-responder fake that, given a script of content-delta chunks ` +
    `+ final tool_calls, yields them incrementally (mirror the _http_factory injection in test_ollama_roundtrip.py) so the ` +
    `loop's incremental rendering is provable WITHOUT Ollama.\n` +
    `7. VALIDATION: feed a 3-content-delta + tool_call script through the streaming-responder double; assert on_delta called ` +
    `>= 3 times IN ORDER AND the returned AssembledResponse EQUALS what chat() would assemble from the same chunks (PARITY). ` +
    `Run "${PYTEST} tests/test_streaming.py -q" and "${PYTEST} tests/test_ollama_roundtrip.py -q"; paste BOTH real pass lines ` +
    `into testsRun. passed=true REQUIRES the parity assert green AND test_ollama_roundtrip.py still green (chat() untouched).\n` +
    `RECOVERY POLICY: if chat()/stream parity cannot be made to hold, set passed=false and explain — transport-level ` +
    `correctness, do NOT paper over.`,
  { label: 'P1-streaming-responder', phase: 'P1: Streaming responder adapter (ollama.py, additive)', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p1.passed !== true) {
  return { status: 'HALTED_AT_P1', reason: 'streaming responder parity with chat() did not hold; transport-level correctness gates the whole spine. Leaving the plan in pending/.', p0, p1 };
}

phase('P2: ReplIO incremental hook + stream drain in run_turn (repl.py)');
const p2 = await agent(
  preamble('2') +
    `Execute Phase 2 (ReplIO INCREMENTAL HOOK + STREAM DRAIN). SINGLE-WRITER repl.py — you edit it now; P3 edits it AFTER ` +
    `you; never assume a concurrent editor. Your slice, touching ONLY core/agent/repl.py, tests/test_streaming.py, and the ` +
    `FakeIO in tests/test_repl.py (for delta capture):\n` +
    `1. Extend the ReplIO Protocol (:65) with OPTIONAL methods: render_delta(token)->None, tool_step(text)->None (used P3), ` +
    `tool_step_result(text)->None (used P3). OPTIONALITY: the loop feature-detects them (hasattr / default no-op) so any ` +
    `ReplIO implementing only render() (today's contract) still works.\n` +
    `2. ConsoleIO (:73) implements render_delta by writing the token with NO trailing newline + flush (tokens appear live), ` +
    `and keeps render() for full-line ENGLISH answers. ALL new strings I2-clean.\n` +
    `3. SEAM (plan Q1 PREFERS this): build_repl will wire the streaming responder's on_delta to repl's io.render_delta; ` +
    `run_turn stays UNAWARE of "streaming vs buffered" because the responder OWNS the sink (keeps run_turn's responder ` +
    `contract intact, A1). When a buffered responder is wired (tests), behavior is BYTE-IDENTICAL to today (no render_delta ` +
    `calls).\n` +
    `4. NO DOUBLE-RENDER (the top risk): if tokens were already streamed via render_delta, the existing ` +
    `self._io.render(verdict.content) at the end of run_turn must NOT re-print the English answer. Resolve explicitly: a ` +
    `streaming IO's render() emits only a trailing newline / no-op when the same content was already streamed; a buffered ` +
    `IO's render() prints in full as today. Assembled ENGLISH text must appear EXACTLY ONCE.\n` +
    `5. A render_delta that RAISES must not kill the turn (P1 wraps the sink; add the guard here too). Add a test where ` +
    `render_delta raises and the turn STILL completes + audits.\n` +
    `6. FakeIO (tests/test_repl.py) gains render_delta capture so SC1 is testable; preserve existing FakeIO.rendered ` +
    `behavior.\n` +
    `7. VALIDATION: SC1 — a chunked streaming responder + streaming FakeIO -> rendered-deltas count == number of content ` +
    `deltas, in order. SC5 — EVERY existing tests/test_repl.py test green (buffered path unchanged) AND the P0 baseline test ` +
    `(tests/test_invariance_baseline.py) green. No-double-render test green. Run "${PYTEST} tests/test_repl.py -q", ` +
    `"${PYTEST} tests/test_streaming.py -q", "${PYTEST} tests/test_invariance_baseline.py -q"; paste all three real pass ` +
    `lines into testsRun. Populate newStrings with any new user-facing strings. passed=true REQUIRES SC1 + no-double-render ` +
    `+ all of test_repl.py + the baseline green.\n` +
    `RECOVERY POLICY: if no-double-render or degrade-on-error cannot be satisfied, set passed=false and explain — loop-spine ` +
    `correctness, do NOT paper over.`,
  { label: 'P2-replio-stream-drain', phase: 'P2: ReplIO incremental hook + stream drain in run_turn (repl.py)', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p2.passed !== true) {
  return { status: 'HALTED_AT_P2', reason: 'ReplIO incremental hook / no-double-render / degrade-on-error not satisfied; loop-spine correctness gates P3. Leaving the plan in pending/.', p0, p1, p2 };
}

phase('P3: Live tool-call display in _dispatch_calls (repl.py)');
const p3 = await agent(
  preamble('3') +
    `Execute Phase 3 (LIVE TOOL-CALL DISPLAY). SINGLE-WRITER repl.py — serialized AFTER P2 (its hooks now exist on ReplIO + ` +
    `ConsoleIO). Your slice, touching ONLY core/agent/repl.py and tests/test_tool_step_display.py:\n` +
    `1. In _dispatch_calls (:574), AROUND each call: place io.tool_step("running: " + synthesize_command(call)) (using ` +
    `synthesize_command :137 — already I2-clean shell argv) AFTER _resolve_gate returns cleared==True and BEFORE ` +
    `_safe_dispatch (:672). A "running:" line must NEVER appear for an op the gate refused/declined (I3 honesty: never imply ` +
    `an unconfirmed write ran). For a refused/declined op, emit tool_step_result with a neutral "not run" status (the ` +
    `gate_note is already I2-clean) — never "running".\n` +
    `2. AFTER dispatch: io.tool_step_result with a terse status derived from ToolResult (exit_code / summary), I2-clean. ` +
    `Speak as a command interface ("done", "exit 0", "no changes", "not run") — never "the agent did X".\n` +
    `3. SC4 — do NOT add, move, or remove any audit.write call, and do NOT touch the gate logic; tool-step is DISPLAY ONLY ` +
    `(adds ZERO audit records, does not alter audit ordering).\n` +
    `4. VALIDATION in tests/test_tool_step_display.py: SC2 — a CONFIRMED-write scripted turn -> FakeIO captured a ` +
    `tool_step("running: ...") BEFORE and a tool_step_result AFTER, and the command in the line matches ` +
    `synthesize_command (use a NON-trivial render, e.g. systemctl status nginx, not just a default-deny floor string). A ` +
    `DECLINED-write turn -> NO "running:" line, a "not run" status line. SC3/I2 — every captured tool_step / ` +
    `tool_step_result string passes prompt._AI_PATTERN. SC4 — the P0 baseline test + audit counts UNCHANGED (display added ` +
    `zero audit records). Run "${PYTEST} tests/test_tool_step_display.py -q" and ` +
    `"${PYTEST} tests/test_invariance_baseline.py -q"; paste both real pass lines into testsRun. Populate newStrings with ` +
    `every tool-step / status string you introduced. passed=true REQUIRES SC2 + SC3 + SC4 audit-count parity green.\n` +
    `RECOVERY POLICY: if SC4 audit-count parity breaks, set passed=false and explain — it means display perturbed the ` +
    `gate/audit ordering, which is a bug; do NOT paper over.`,
  { label: 'P3-tool-step-display', phase: 'P3: Live tool-call display in _dispatch_calls (repl.py)', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p3.passed !== true) {
  return { status: 'HALTED_AT_P3', reason: 'live tool-step display broke SC2/SC3 or SC4 audit-count parity; the gate/audit invariance is safety-critical. Leaving the plan in pending/.', p0, p1, p2, p3 };
}

// ===================================================================
// HARVEST the parallel pair (P4, P5) before the P6 join. They have been
// running in the background concurrent with P0->P3.
// ===================================================================
log('Spine P0->P3 complete; harvesting the parallel prose pair P4 (prompt.py) + P5 (router.py).');
const [p4, p5] = await Promise.all([p4Promise, p5Promise]);
if (p4.passed !== true) {
  return { status: 'HALTED_AT_P4', reason: 'prompt discipline + few-shot did not pass (I2 import-check / SC6 / wire-shape parity). Leaving the plan in pending/.', p0, p1, p2, p3, p4, p5 };
}
if (p5.passed !== true) {
  return { status: 'HALTED_AT_P5', reason: 're-ask tightening did not pass (test_router.py / I2 / frozen-shape). Leaving the plan in pending/.', p0, p1, p2, p3, p4, p5 };
}

// ===================================================================
// P6 — Integration wiring (opus agent) THEN the SC4 invariance gate via the
// audit-duo WORKFLOW (real fan-out; opus reviewers; NOT consensus-verification-duo).
// ===================================================================
phase('P6: Integration wiring + invariance gate + full-suite green');
const p6wire = await agent(
  preamble('6') +
    `Execute Phase 6 (INTEGRATION WIRING + INVARIANCE PROOF). The spine (P1/P2/P3) and prose (P4/P5) all landed; this is the ` +
    `JOIN. main.py is the only NEW write; repl.py is READ/verify-only here (its edits landed in P2/P3). Touch ` +
    `core/agent/main.py and a consolidated test file (e.g. extend tests/test_streaming.py or add ` +
    `tests/test_integration_invariance.py):\n` +
    `1. Wire build_repl (:166): replace the buffered closure that returns client.chat(...) at :181 in the LIVE path with the ` +
    `P1 STREAMING responder, its on_delta sink pointed at the ConsoleIO render_delta (P2). KEEP THE BUFFERED PATH REACHABLE ` +
    `for SC5/back-compat — a clean default or an ERDTREE_STREAM flag (default ON for the live ConsoleIO path, buffered for ` +
    `injected responders). test_main.py must stay green.\n` +
    `2. VERIFY shell/shell.py: the dead-man guard still WRAPS the (now-streaming) turn; a ConnectionError still triggers the ` +
    `bash fallback; NO new unbounded wait introduced (I9). This is verify-only — do not edit shell.py unless I9 is actually ` +
    `broken (and if so, that is an escalation, not a silent fix).\n` +
    `3. SC4 INVARIANCE PROOF: re-run the Phase-0 oracle (import/re-run tests/test_invariance_baseline.py's scripted turns) ` +
    `against the FULLY-WIRED streaming path and assert gate decisions + audit records + TurnOutcome are IDENTICAL to the ` +
    `pinned "before" values. Do NOT re-derive the oracle — reuse P0's.\n` +
    `4. CONSOLIDATED I2 INVENTORY (SC3 belt-and-suspenders): collect EVERY new user-facing string across P2/P3/P4/P5 (see ` +
    `the newStrings each phase reported) and assert each passes prompt._AI_PATTERN in one test.\n` +
    `5. DEV-HOST HONESTY: assert NO live Ollama round-trip; note in the test docstring that live FEEL is reasoned + ` +
    `double-proven and the real round-trip is DEFERRED-TO-MOSSAD.\n` +
    `6. Run the FULL suite: "${PYTEST} -q" — confirm >=1795 prior tests + the new ones GREEN. Also run ` +
    `"${PYTEST} tests/test_main.py tests/test_deadman.py -q" explicitly (I9 intact). Paste the real full-suite pass line + ` +
    `the SC4 equality assertion into testsRun and the evidence file. passed=true REQUIRES the full suite green, SC4 equality ` +
    `holding, and test_main.py + test_deadman.py green.`,
  { label: 'P6-integration-wiring', phase: 'P6: Integration wiring + invariance gate + full-suite green', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p6wire.passed !== true) {
  return { status: 'HALTED_AT_P6_WIRING', reason: 'integration wiring failed: full suite not green, or SC4 invariance equality did not hold, or I9 dead-man guard broke. The buffered->streaming swap must not pass buffered tests while breaking the live path. Leaving the plan in pending/.', p0, p1, p2, p3, p4, p5, p6wire };
}

// SC4 is the load-bearing safety claim -> real, genuinely-independent adversarial
// confirmation via the audit-duo WORKFLOW. Reviewers pinned to OPUS (sonnet had an
// outage this session). A null/errored reviewer => the workflow returns/we treat as
// UNRESOLVED => ESCALATE; never a silent pass.
phase('P6 gate: audit-duo invariance verification (SC4)');
let duo;
try {
  duo = await workflow('audit-duo', {
    claim:
      'The Erdtree harness streaming upgrade is PRESENTATION-ONLY and preserves SC4 exactly: with the streaming responder ' +
      'wired into build_repl, (A) the loop STILL assembles a full AssembledResponse-equivalent BEFORE routing/gating/ ' +
      'dispatch, so the router/permission gate/audit see the SAME assembled turn as the buffered path; (B) re-running the ' +
      'Phase-0 "before" oracle against the streaming path yields IDENTICAL gate decisions (permissions.classify outcomes), ' +
      'IDENTICAL audit records (count AND content — no audit.write added/moved/removed), and IDENTICAL TurnOutcome ' +
      '(tool_calls_made, refused, misses, rounds); (C) a streamed content token NEVER represents an unconfirmed write — the ' +
      '"running: <cmd>" line is emitted ONLY after the gate clears, declined/refused ops show "not run" and never "running"; ' +
      '(D) the final English answer renders EXACTLY ONCE (no double-render, no missing output); (E) the dead-man bash ' +
      'fallback (I9) still wraps every turn and still catches ConnectionError with no new unbounded wait; (F) every NEW ' +
      'user-facing string (token render path, "running:"/result lines, few-shot prose, re-ask wording) passes the I2 ' +
      'filter (prompt._AI_PATTERN — no ai/llm/model/agent/agentic/inference/ollama); (G) streaming reuses the existing ' +
      'loopback-asserted OllamaClient with NO new socket/host (I1); and (H) the buffered responder + ConsoleIO path is still ' +
      'the default and the full suite (>=1795 tests) is green.',
    context:
      'Repo ' + REPO + '. This is a LINUX host with pytest in the project venv — RE-RUN the tests yourself, do NOT trust ' +
      'the reported tally. Run the full suite with "' + PYTEST + ' -q" and the invariance test with ' +
      '"' + PYTEST + ' tests/test_invariance_baseline.py -q" (and tests/test_integration_invariance.py if present). Read: ' +
      'core/model/ollama.py (the P1 streaming responder + UNCHANGED chat()/stream()), core/agent/repl.py (P2 ReplIO ' +
      'render_delta/tool_step hooks + run_turn drain + the no-double-render render() resolution + P3 tool-step display in ' +
      '_dispatch_calls :574, _resolve_gate :635, _safe_dispatch :672 — the gate/audit ordering must be untouched), ' +
      'core/agent/main.py (build_repl :166 streaming wiring with the buffered path still reachable), core/agent/prompt.py ' +
      '(P4 few-shot + _assert_no_ai_language :64), core/agent/router.py (P5 re-ask wording, frozen TurnKind/role:"tool" ' +
      'shape), shell/shell.py (I9 dead-man guard), and the P0 oracle tests/test_invariance_baseline.py. Plan: §0 (SC4), §1, ' +
      '§3 Phase 6 of ' + PLAN + '. ADVERSARIALLY hunt: (1) ANY input/turn where the streaming path produces a DIFFERENT ' +
      'gate decision, a different audit record count/content, or a different TurnOutcome than the P0 oracle; (2) ANY path ' +
      'where a "running:" line (or a streamed token) appears for an op the gate refused/declined — i.e. implies an ' +
      'unconfirmed write ran; (3) a double-rendered or missing final English answer; (4) a new unbounded wait or a swallowed ' +
      'ConnectionError that defeats the dead-man fallback; (5) ANY new user-facing string that leaks an I2 forbidden term; ' +
      '(6) any new socket/host in the streaming responder. Verdict PASS only if you cannot construct ANY of these; FAIL ' +
      'with the concrete counter-example otherwise. If a reviewer is unavailable/errors and you cannot genuinely ' +
      'cross-examine, report UNRESOLVED (an honest split) — never a manufactured PASS.',
    maxRounds: 3,
    model: 'opus',
    schema: duoSchema,
  });
} catch (err) {
  duo = { verdict: 'UNRESOLVED', findings: ['audit-duo workflow errored: ' + String(err && err.message ? err.message : err)], summary: 'audit-duo could not complete (likely a model-availability/API error). Treated as UNRESOLVED per the model-availability policy — never a silent pass on the SC4 safety gate.' };
}
if (!duo || duo.verdict == null || duo.verdict === 'UNRESOLVED') {
  return {
    status: 'ESCALATE_UNRESOLVED_SPLIT',
    reason: 'SC4 invariance (gate/audit/dead-man equivalence under streaming) did NOT clear genuinely-independent adversarial ' +
      'verification — the two reviewers did not converge, or a reviewer was unavailable (a null/errored reviewer is treated ' +
      'as UNRESOLVED, NEVER a silent pass). This is the load-bearing safety claim and must not be rationalized. Leaving the ' +
      'plan in pending/. Re-run when model availability is restored, pinning reviewers to opus.',
    duo, p0, p1, p2, p3, p4, p5, p6wire,
  };
}
if (duo.verdict !== 'PASS') {
  return {
    status: 'HALTED_AT_P6_DUO',
    reason: 'audit-duo found an SC4 / I2 / I9 / I1 counter-example: streaming is NOT byte-behavior presentation-only. ' +
      'Gate/audit/dead-man equivalence is non-negotiable and is never auto-skipped. Leaving the plan in pending/.',
    duo, p0, p1, p2, p3, p4, p5, p6wire,
  };
}

// ===================================================================
// F — Archive the plan ONLY on full success. This workflow executes the
// ENTIRE P0-P6 plan, so a full pending->archive move is correct here.
// ===================================================================
phase('F: Archive plan on success');
const archive = await agent(
  `cd ${REPO}. The Erdtree Harness UX Upgrade plan (P0-P6) has passed EVERY gate: P0 baseline pinned; the streaming spine ` +
    `P1 (ollama.py additive streaming responder, chat() parity) -> P2 (ReplIO render_delta + no-double-render) -> P3 (live ` +
    `tool-step display, SC4 audit-count parity) landed serially; P4 (prompt discipline + few-shot, I2 + wire-shape parity) ` +
    `and P5 (tighter re-ask, frozen shape) landed in parallel; P6 wired build_repl (buffered path reachable), proved the ` +
    `SC4 invariance equality, kept the full suite green, and the SC4 safety claim cleared genuinely-independent audit-duo ` +
    `verification.\n` +
    `1. Append a final rollup to ${AUDIT_DIR}/FINAL.md (create the dir/file if missing): list the files created ` +
    `(tests/test_invariance_baseline.py, tests/test_streaming.py, tests/test_tool_step_display.py, ` +
    `tests/test_prompt_fewshot.py, and any tests/test_integration_invariance.py) and modified (core/model/ollama.py, ` +
    `core/agent/repl.py, core/agent/prompt.py, core/agent/router.py, core/agent/main.py), the exact ${PYTEST} commands + ` +
    `tallies, the SC4 invariance-equality result, the audit-duo PASS, and the honestly-deferred item (live 7B/14B Ollama ` +
    `round-trip FEEL -> DEFERRED-TO-MOSSAD).\n` +
    `2. This workflow executed the ENTIRE plan (P0-P6), so per the Erdtree lifecycle flow (pending/plans = "not yet built", ` +
    `archive/plans = "built") MOVE the plan file: ${PLAN} -> ${PLAN_ARCHIVE} (use git mv if the tree is a git repo, else a ` +
    `plain move; create the archive/plans dir if needed). Confirm the file now resides in archive/ and no longer in ` +
    `pending/.\n` +
    `Print a one-line summary and exit.`,
  { label: 'F-archive', phase: 'F: Archive plan on success', model: 'haiku', agentType: 'general-purpose',
    schema: { type: 'object', required: ['done', 'summary'], properties: { done: { type: 'boolean' }, planLocation: { type: 'string' }, summary: { type: 'string' } } } }
);

return {
  status: 'HARNESS_UX_COMPLETE',
  built: [
    'core/model/ollama.py — additive streaming responder (drains stream(), on_delta sink, chat() parity; chat() untouched)',
    'core/agent/repl.py — ReplIO render_delta/tool_step/tool_step_result + run_turn stream drain (no double-render) + live tool-step display in _dispatch_calls (post-gate only)',
    'core/agent/prompt.py — tool-use discipline block + small-model few-shot (I2-clean, wire-shape-parity)',
    'core/agent/router.py — tighter instructive re-ask wording (frozen TurnKind/role:"tool" shape)',
    'core/agent/main.py — build_repl wires the streaming responder (buffered path kept reachable)',
    'tests: test_invariance_baseline.py (P0 oracle), test_streaming.py, test_tool_step_display.py, test_prompt_fewshot.py',
  ],
  verified: 'SC1 incremental render, SC2 running/result lines, SC3 I2 of every new string, SC4 gate/audit/TurnOutcome IDENTICAL to the P0 oracle under streaming (confirmed by audit-duo), SC5 buffered path + full suite green, SC6 discipline+few-shot present & wire-shape-valid, I1 no new socket, I9 dead-man guard intact.',
  duoVerdict: duo.verdict,
  deferred: ['live 7B/14B Ollama round-trip FEEL (token-by-token stream, running-line ordering, I2 read-through on a real model) -> DEFERRED-TO-MOSSAD: needs a provisioned Linux box with Ollama running a real model; this plan proves the harness with scripted/chunked-responder doubles.'],
  planLocation: archive && archive.planLocation ? archive.planLocation : (PLAN_ARCHIVE + ' (whole P0-P6 plan executed -> archived)'),
  note: 'The Erdtree harness now streams model English token-by-token, shows live "running: <cmd>"/result steps, carries a small-model-tuned tool-use prompt + few-shot, and a tighter self-correcting re-ask — all PRESENTATION-ONLY: the permission gate, audit spine, and dead-man fallback are byte-behavior-unchanged (SC4), proven against the frozen P0 oracle and cleared by adversarial audit-duo verification. Live-model FEEL on the 7B/14B is the only deferred item (bench/fine-tune track, 0001 Phase-10).',
};
