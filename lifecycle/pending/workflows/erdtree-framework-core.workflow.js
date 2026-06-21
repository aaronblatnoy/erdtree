// Erdtree framework-core buildout — focused, dev-host-honest workflow.
// Scope: our OWN direct LLM->CLI framework (context, tools, permission seam, audit,
//   agent loop, shell dispatch, dead-man, invisible memory, tiers) on BASE Qwen via Ollama.
// Claude Code + OpenCode = inspiration only (vendor/), never shipped/imported.
// DEFERRED (out of scope here): P7 RAG, P10 training/fine-tune, P11 installer/ISO/shipping.
// Principle: this macOS dev host WRITES code + unit/mock tests; anything needing a live
//   model or real Linux is marked DEFERRED-TO-MOSSAD — NEVER fabricated.

export const meta = {
  name: 'erdtree-framework-core',
  description: 'Build the Erdtree framework core: our own direct LLM-to-CLI interaction engine (context layer, Linux tool abstraction, permission seam, audit spine, agent loop, shell dispatch, dead-man fallback, invisible memory, tier plumbing) on base Qwen via local Ollama. Claude Code and OpenCode are inspiration only, never shipped. RAG, fine-tuning, and ISO/shipping are deferred. The macOS dev host writes the code and unit-tests it; live model and Linux validation are deferred to the mossad server and never fabricated.',
  phases: [
    { title: 'P0: Framework Spec + Decision Docs', detail: 'Record the build-our-own decision; freeze OUR tool-call contract (0002) informed by the reference harnesses + Ollama. Single, opus.' },
    { title: 'P1: Safety & System-Awareness Core', detail: 'context collector, permission classifier (opus keystone, audit-duo verified), append-only audit. 3-way worktree fanout.' },
    { title: 'P2: Core Tools (services, packages, logs)', detail: 'registry frozen, then 3-way tool fanout. Linux tools; code + mocked tests on the dev host.' },
    { title: 'P3: Model Wiring (Ollama + prompt)', detail: 'localhost Ollama client + prompt assembly on base Qwen. Code + mock test; live round-trip deferred to mossad.' },
    { title: 'P4: The Agent Loop + Benchmark Harness', detail: 'router/repl/main/context close the loop + the tool-call validity benchmark harness. Code complete + unit-tested; live measurement deferred to mossad.' },
    { title: 'P5: Shell + Command/English Dispatch + Dead-Man Fallback', detail: 'login shell, never-mistranslate dispatch, loud bash dead-man. Logic unit-tested on the dev host (audit-duo verified); live integration deferred.' },
    { title: 'P6: Remaining Tools', detail: '7-way worktree fanout; lockout/data-loss tools opus. Code + mocked tests.' },
    { title: 'P8: Invisible Memory / Compaction', detail: 'task-scoped context cycling + compaction + per-host facts. Audit-log episodic recall deferred with RAG. Fully unit-testable here.' },
    { title: 'P9: Tier Plumbing (Marika + Radagon) + ERDTREE_TIER', detail: 'tier loader + core/ de-hardcode (refractor-trio, grep-clean), then 2-way tier-config fanout. Both tiers on base Qwen.' },
    { title: 'Finalize: rollup + mossad deploy runbook', detail: 'FINAL.md rollup + a concrete deploy/smoke-test runbook for mossad. Plan stays in pending (partial buildout).' },
  ],
};

const REPO = '/Users/aaron_7nh0yzm/erdtree';
const PLAN = REPO + '/lifecycle/pending/plans/erdtree-v0.1-buildout.txt';
const CLAUDE_MD = REPO + '/CLAUDE.md';
const AUDIT_DIR = REPO + '/lifecycle/archive/audits/erdtree-framework-core';

const passSchema = {
  type: 'object',
  required: ['passed', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    deferred: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

function preamble(phaseId) {
  return (
    `IMPORTANT — REPO ROOT: the Erdtree repo is at ${REPO}. Your shell CWD may be elsewhere, so FIRST run ` +
    `cd ${REPO}, and treat EVERY relative file path below as relative to that repo root (e.g. ` +
    `"core/agent/permissions.py" means ${REPO}/core/agent/permissions.py). ` +
    `Before anything: read ${CLAUDE_MD} (canonical context + Load-Bearing Invariants) and the relevant phase of ${PLAN}. ` +
    `DEV-HOST MODE: you are on a macOS host with NO Ollama, NO GPU, and NO Linux OS integration (systemctl/dnf/journalctl/` +
    `systemd/pam/firewalld do NOT exist here). WRITE the framework code + unit tests; MOCK anything that needs a live model ` +
    `or Linux, and test against fixtures. NEVER fabricate a live result, a benchmark number, or a passing integration run — ` +
    `a prior agent did exactly that and was refuted. For any validation that needs a running model or real Linux, WRITE the ` +
    `test and mark it DEFERRED-TO-MOSSAD in your evidence. passed=true means: the code is complete AND its unit/mock tests ` +
    `are green, with live items honestly deferred (list them in the 'deferred' field). ` +
    `FRAMING: the PRODUCT is Erdtree's OWN framework in core/. Claude Code (vendor/claude-code) and OpenCode ` +
    `(vendor/opencode) are INSPIRATION ONLY — study how they do the agentic loop / tool-use / terminal UX, but NEVER import, ` +
    `vendor, or ship them. Keep core/ harness-portable and model-portable; it must only ever talk to localhost Ollama ` +
    `(I1, by construction). Invariants: I1 localhost-only egress; I2 no AI/LLM/model/agent language in user-facing strings; ` +
    `I3 permission gate before every write/destructive (destructive = literal-word-typed, never auto-confirm, never ` +
    `non-interactive); I4 append-only JSONL audit of every op; I5 system context always injected; I6 core/ never hardcodes a ` +
    `tier/product name (ERDTREE_TIER selects); I8 simple ops feel instant; I9 dead-man bash fallback. ` +
    `Write your evidence (what you built, tests + output, what is deferred) to ${AUDIT_DIR}/phase-${phaseId}.md. ` +
    `Print a one-line summary and exit.\n\n`
  );
}

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log('Erdtree framework-core buildout starting (dev-host writes; mossad validates; no fabrication).');

// ===================================================================
// P0 — Framework spec + decision docs. SINGLE, opus.
// ===================================================================
phase('P0: Framework Spec + Decision Docs');
const p0 = await agent(
  preamble('0') +
    `Execute Phase 0 (re-scoped). The harness question is RESOLVED: we build our OWN framework, with ` +
    `vendor/claude-code and vendor/opencode as INSPIRATION ONLY (study their agentic loop / tool-use / terminal UX; do ` +
    `NOT import or ship them). Produce: (1) docs/decisions/0001-framework.md — the build-our-own decision + rationale ` +
    `(clean by construction: localhost-only, invisible-AI, no third-party license or telemetry baggage); note Claude Code ` +
    `is NO-GO to ship (proprietary + cloud-bound) and OpenCode is MIT inspiration. (2) docs/decisions/0002-tool-call-` +
    `protocol.md — FREEZE OUR framework's tool-call contract, informed by reading vendor/opencode/packages/llm/src/` +
    `protocols/openai-compatible-chat.ts + openai-chat.ts and packages/llm/src/tool.ts + tool-runtime.ts, and GROUNDED in ` +
    `Ollama's /v1/chat/completions function-calling format: request shape, tool_calls parsing, tool-result messages, SSE ` +
    `delta assembly, malformed/re-ask handling, and the tool-call validity definition. Cite real reference file paths; all ` +
    `machine-consumed JSON examples must parse. Keep the contract framework-level (portable), not OpenCode-internal. ` +
    `(3) bench/README.md + ~10 seed bench/cases/*.json (the validity-rate definition + representative cases). Touch only ` +
    `docs/decisions/ and bench/. passed=true iff 0002 is parseable and faithful to Ollama's real format.`,
  { label: 'P0-framework-spec', phase: 'P0', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p0.passed !== true) {
  return { status: 'HALTED_AT_P0', reason: 'framework spec / 0002 tool-call contract not sound.', p0 };
}
const PROTO = 'the frozen tool-call contract in docs/decisions/0002-tool-call-protocol.md (do not re-derive it)';

// ===================================================================
// P1 — Safety & system-awareness core. 3-way worktree fanout. opus on permissions.
// ===================================================================
phase('P1: Safety & System-Awareness Core');
const p1Brief = (slice, extra) =>
  preamble('1') +
  `Execute Phase 1. Your slice: ${slice}. Touch ONLY your file(s) + its test. No tier names anywhere (I6). ${extra}`;
const [p1ctx, p1perm, p1audit] = await parallel([
  () => agent(
    p1Brief(
      'core/context/{collector,snapshot,cache}.py + tests/test_snapshot.py',
      'collector reads /proc, /sys, systemctl, rpm -qa, ss, etc. — on macOS these do not exist, so WRITE the Linux calls ' +
        'and TEST against fixtures (live collection deferred to mossad). Typed snapshot cheap to serialize into the prompt; ' +
        'short-TTL cache is a latency optimization only (the live box stays source of truth). passed iff test_snapshot is ' +
        'green against fixtures.'
    ),
    { label: 'P1-context', phase: 'P1', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  ),
  () => agent(
    p1Brief(
      'core/agent/permissions.py + tests/test_permissions.py',
      'KEYSTONE (pure logic — FULLY testable on this dev host): classify read/write/destructive; read=instant, ' +
        'write=confirm, destructive=literal-word-typed-in-full, NEVER auto-confirm, NEVER non-interactive; default-deny on ' +
        'ambiguity (unknown write-shape => write-confirm, unknown destructive-shape => destructive). Explicit destructive ' +
        'taxonomy (rm -rf, mkfs, dd, partition ops, user/SSH/firewall lockout, remote reboot). passed iff a curated ' +
        'destructive corpus is ALWAYS gated and NEVER auto-confirmable, and non-interactive destructive is refused (I3).'
    ),
    { label: 'P1-permissions', phase: 'P1', model: 'opus', agentType: 'general-purpose', schema: passSchema }
  ),
  () => agent(
    p1Brief(
      'core/agent/audit.py + tests/test_audit.py',
      'append-only JSONL writer (ts, tier, nl_input, translated_command, tool, args, permission_decision, exit_code, ' +
        'stdout_summary, stderr_summary, result); fsync-on-write; atomic; survives crash mid-write. Fully testable here. ' +
        'passed iff exactly one parseable JSONL line per op, append-only, partial-write recovery verified (I4).'
    ),
    { label: 'P1-audit', phase: 'P1', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  ),
]);
if (p1perm.passed !== true) {
  return { status: 'HALTED_AT_P1', reason: 'permissions classifier failed (safety gate).', p1perm };
}
const p1Audit = await workflow('audit-duo', {
  claim:
    'core/agent/permissions.py NEVER under-gates: no destructive op (rm -rf, mkfs, dd, partition, SSH/firewall/user ' +
    'lockout, remote reboot) slips through as a mere write-confirm or auto-confirms, and no path lets a destructive op ' +
    'run non-interactively.',
  context:
    `core/agent/permissions.py + tests/test_permissions.py. Adversarially HUNT a destructive op the classifier mis-files ` +
    `as write (under-gating is catastrophic on a live box, I3).`,
});
if (p1Audit.verdict !== 'CONFIRMED') {
  return { status: 'HALTED_AT_P1_AUDIT', reason: `permissions audit-duo returned ${p1Audit.verdict} (no manufactured consensus).`, p1Audit };
}
if (p1ctx.passed !== true || p1audit.passed !== true) {
  return { status: 'HALTED_AT_P1', reason: 'context/ or audit.py validation failed.', p1ctx, p1audit };
}

// ===================================================================
// P2 — registry first (SEQ), then 3-way tool fanout. sonnet.
// ===================================================================
phase('P2: Core Tools (services, packages, logs)');
const p2reg = await agent(
  preamble('2') +
    `Execute Phase 2, the REGISTRY slice ONLY: core/tools/__init__.py — a tool registry + uniform interface (name, args ` +
    `schema, per-op permission class read|write|destructive, execute()->structured result {exit_code, stdout, stderr, ` +
    `summary}). This is the FROZEN shared contract router.py (P4) and every tool bind to. Touch only core/tools/__init__.py. ` +
    `passed iff the interface is importable and a stub tool round-trips through it.`,
  { label: 'P2-registry', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (p2reg.passed !== true) {
  return { status: 'HALTED_AT_P2', reason: 'tool registry/interface did not freeze; blocks tool fanouts.', p2reg };
}
const TOOLIF = 'the frozen tool interface in core/tools/__init__.py (do not redefine it)';
const p2Brief = (name, extra) =>
  preamble('2') +
  `Execute Phase 2. Your slice: core/tools/${name}.py against ${TOOLIF}. Route EVERY execute() through permissions + audit ` +
  `(P1). Return STRUCTURED results. dnf NOT apt; SELinux-aware. These are Linux tools — on macOS, MOCK the subprocess ` +
  `calls and test with fixtures (live execution deferred to mossad). ${extra} Touch only your tool + tests/test_tools_` +
  `${name}.py. passed iff test_tools_${name} is green against mocks.`;
const [p2svc, p2pkg, p2log] = await parallel([
  () => agent(p2Brief('services', 'systemctl status/start/stop/restart/enable/logs; restart=write-confirm; mask=write.'),
    { label: 'P2-services', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
  () => agent(p2Brief('packages', 'dnf install/remove/update/search/info; a remove whose transaction plan removes kernel/SSH = destructive; surface the dnf transaction summary in the confirm.'),
    { label: 'P2-packages', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
  () => agent(p2Brief('logs', 'journalctl + dmesg query/filter/tail/since; surface audit2allow-style hints for SELinux denials.'),
    { label: 'P2-logs', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
]);
const p2deferred = [p2svc, p2pkg, p2log].filter((r) => r.passed !== true).map((r) => r.summary);
if (p2deferred.length) log(`P2 deferred tool(s): ${p2deferred.join(' | ')}`);

// ===================================================================
// P3 — Ollama + prompt. SINGLE, sonnet.
// ===================================================================
phase('P3: Model Wiring (Ollama + prompt)');
const p3 = await agent(
  preamble('3') +
    `Execute Phase 3. Build core/model/ollama.py (streaming client to LOCAL Ollama via the OpenAI-compatible endpoint; ` +
    `model + base URL from tier config; PINNED tag never :latest; ASSERT it only talks to localhost — I1) and ` +
    `core/agent/prompt.py (assemble: house system prompt with no-hedge voice and NO AI language per I2 + tier prompt + ` +
    `fresh injected context per I5 + input + recent history, in ${PROTO}; tier text stubbed until P9). DEV-HOST: there is no ` +
    `Ollama here — unit-test the client against a MOCK OpenAI-compatible server and ASSERT localhost-only; the live ` +
    `base-Qwen round-trip is DEFERRED-TO-MOSSAD. Touch only core/model/ollama.py, core/agent/prompt.py, ` +
    `tests/test_ollama_roundtrip.py. passed iff the mock round-trip parses a well-formed tool call and localhost-only is ` +
    `asserted.`,
  { label: 'P3-model-wiring', phase: 'P3', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (p3.passed !== true) {
  return { status: 'HALTED_AT_P3', reason: 'model wiring / prompt assembly failed.', p3 };
}

// ===================================================================
// P4 — Close the loop + benchmark harness. SEQUENTIAL, opus.
// ===================================================================
phase('P4: The Agent Loop + Benchmark Harness');
const p4 = await agent(
  preamble('4') +
    `Execute Phase 4 — the integration spine. Build core/agent/router.py (parse tool calls strictly against ${PROTO}; ` +
    `reject malformed calls + surface a re-ask path; count a bad call as a MISS, never crash), core/agent/context.py ` +
    `(per-turn context plumbing), core/agent/repl.py (the read-eval-print loop), core/agent/main.py (wire collector -> ` +
    `prompt -> ollama -> router -> permissions -> tools -> audit -> back to model). Build bench/run_bench.py + ` +
    `bench/cases/*.json: the tool-call validity benchmark (% of turns emitting a valid, parseable tool call). DEV-HOST: the ` +
    `router parsing AND the benchmark RUNNER are fully unit-testable here against recorded/mock model outputs — do that. The ` +
    `LIVE validity measurement across base Qwen 14B/7B/3B is DEFERRED-TO-MOSSAD; do NOT fabricate a rate. Touch only ` +
    `core/agent/{router,context,repl,main}.py + bench/. passed iff router unit tests are green (valid calls parse, ` +
    `malformed counted as a miss) AND the benchmark runner executes against mock outputs; live rates deferred.`,
  { label: 'P4-agent-loop', phase: 'P4', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p4.passed !== true) {
  return { status: 'HALTED_AT_P4', reason: 'agent loop / router / benchmark harness incomplete.', p4 };
}

// ===================================================================
// P5 — Shell + dispatch + dead-man. SEQUENTIAL, opus. Cardinal UX + safety.
// ===================================================================
phase('P5: Shell + Command/English Dispatch + Dead-Man Fallback');
const p5 = await agent(
  preamble('5') +
    `Execute Phase 5 (seamless, never-mistranslate, dead-man). Build shell/shell.py (the LOGIN shell: dispatch — an ` +
    `already-valid command runs RAW transparently, English intent translates, NEVER mistranslate per SC4; ambiguous prefers ` +
    `safe behavior and never silently guesses; there is no "AI mode" to enter), shell/passthrough.py (the '!' raw-bash ` +
    `escape), shell/hooks/, and minimal os/ STUBS (systemd unit templates + pam/journald/dmesg hook stubs — full OS ` +
    `integration is deferred to mossad). DEAD-MAN FALLBACK (I9): shell.py's very first action is a guarded agent-start; ANY ` +
    `failure (crash / Ollama down / model mid-pull) -> exec bash automatically with a LOUD banner explaining the degraded ` +
    `state. DEV-HOST: the dispatch logic AND the dead-man fallback are unit-testable WITHOUT a live model (simulate an ` +
    `agent-start failure) — test them fully here; the live "kill Ollama mid-session" integration is DEFERRED-TO-MOSSAD. ` +
    `Touch only shell/, os/, tests/test_dispatch.py, tests/test_deadman.py. passed iff test_dispatch has 0 mis-dispatches ` +
    `on the command-vs-English corpus (SC4) AND test_deadman shows a simulated agent-start failure execs bash loudly (I9).`,
  { label: 'P5-shell-deadman', phase: 'P5', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p5.passed !== true) {
  return { status: 'HALTED_AT_P5', reason: 'dispatch / dead-man failed (safety + UX gate).', p5 };
}
const p5Audit = await workflow('audit-duo', {
  claim:
    'The Phase-5 dispatch NEVER mis-dispatches (no input makes a raw command translate or an English intent run as a ' +
    'guessed raw command), AND no simulated failure (agent crash / Ollama down / model mid-pull) leaves the user ' +
    'shell-less or with a quiet/uninformative fallback.',
  context: `shell/shell.py, shell/passthrough.py, tests/test_dispatch.py, tests/test_deadman.py. Hunt a mis-dispatch input and a shell-less failure mode.`,
});
if (p5Audit.verdict !== 'CONFIRMED') {
  return { status: 'HALTED_AT_P5_AUDIT', reason: `dispatch+dead-man audit-duo returned ${p5Audit.verdict}.`, p5Audit };
}

// ===================================================================
// P6 — Remaining tools. 7-way worktree fanout.
// ===================================================================
phase('P6: Remaining Tools');
const p6Spec = (name, model, extra) => ({
  name, model,
  brief:
    preamble('6') +
    `Execute Phase 6. Your slice: core/tools/${name}.py against ${TOOLIF}. Declare per-op permission classes; ` +
    `lockout/data-loss ops = destructive (be MORE conservative than a coding agent — a live box has no git-undo). MOCK ` +
    `subprocess on macOS; live execution deferred to mossad. ${extra} Touch only your tool + its slice of ` +
    `tests/test_tools_phase6.py. passed iff your test slice is green against mocks; lockout-class ops require the literal ` +
    `destructive confirmation.`,
});
const p6Specs = [
  p6Spec('firewall', 'opus', 'firewalld — SSH-lockout risk named explicitly in the confirm; strictest gate.'),
  p6Spec('users', 'opus', 'user/group ops — locking the only admin is irreversible lockout; strictest gate.'),
  p6Spec('disk', 'opus', 'mkfs/partition/dd = data loss; always destructive-typed.'),
  p6Spec('network', 'sonnet', 'dropping the active link = remote lockout; treat as destructive.'),
  p6Spec('processes', 'sonnet', 'kill/signal; killing critical pids is high blast radius.'),
  p6Spec('hardware', 'sonnet', 'mostly read (lscpu/lsblk/lspci/sensors).'),
  p6Spec('files', 'sonnet', 'rm/chmod/chown on system paths can be destructive — classify conservatively.'),
];
const p6Results = await parallel(
  p6Specs.map((s) => () => agent(s.brief, {
    label: `P6-${s.name}`, phase: 'P6', model: s.model, agentType: 'general-purpose', schema: passSchema,
  }))
);
const p6deferred = p6Specs
  .map((s, i) => ({ name: s.name, r: p6Results[i] }))
  .filter((x) => x.r.passed !== true)
  .map((x) => `${x.name}: ${x.r.summary}`);
if (p6deferred.length) log(`P6 deferred tool(s) (non-blocking): ${p6deferred.join(' | ')}`);

// ===================================================================
// P8 — Invisible memory / compaction. SEQUENTIAL, opus. RAG-independent scope.
// ===================================================================
phase('P8: Invisible Memory / Compaction');
const p8 = await agent(
  preamble('8') +
    `Execute Phase 8 (memory UX), RAG-INDEPENDENT scope (P7 RAG is deferred). Build core/agent/memory.py (TASK-scoped, not ` +
    `session-scoped, context; rolling compaction that KEEPS tool-call OUTCOMES and DROPS verbose raw outputs once reasoned ` +
    `over; keeps recent turns verbatim for deixis like "restart it" / "the one we just did"; compaction threshold = a ` +
    `per-tier config knob) + core/context/facts.py (a tiny curated per-host facts preamble). Design against the "amnesia ` +
    `moment": NEVER surface a context limit/reset, never say "out of context", never ask the user to re-explain something ` +
    `established (I2/UX). The audit-log episodic-recall feature is DEFERRED with RAG — leave a clean, documented seam (a ` +
    `hook) for it; do NOT build a retriever. DEV-HOST: fully unit-testable here. Touch only core/agent/memory.py, ` +
    `core/context/facts.py, tests/test_compaction.py. passed iff test_compaction shows: exceeding the window across many ` +
    `tasks continues with no visible reset; recent-turn deixis still resolves; no "out of context" leakage.`,
  { label: 'P8-memory', phase: 'P8', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p8.passed !== true) {
  return { status: 'HALTED_AT_P8', reason: 'invisible-memory failed (an amnesia leak is the cardinal UX sin).', p8 };
}

// ===================================================================
// P9 — Tier plumbing. refractor-trio de-hardcode, then 2-way content fanout.
// ===================================================================
phase('P9: Tier Plumbing (Marika + Radagon) + ERDTREE_TIER');
const p9refactor = await workflow('refractor-trio', {
  refactor:
    'Build core/agent/tier.py (reads ERDTREE_TIER, loads /etc/{tier}/config.yaml, resolves base-model tag, prompt path, ' +
    'tools allowlist, compaction threshold) and DE-HARDCODE core/: move every hardcoded tier/product name ("marika"/' +
    '"radagon") and any Rocky branding out of core/ into tiers/ so ERDTREE_TIER selects everything at runtime (I6/I7).',
  scope: `${REPO}/core + ${REPO}/tiers + core/agent/tier.py`,
  verify:
    `grep -rEi "marika|radagon|rocky" ${REPO}/core returns ZERO user-facing hardcoded tier/product/Rocky strings, AND ` +
    `pytest tests/test_tier_loader.py passes (ERDTREE_TIER=marika vs radagon loads distinct config).`,
});
const p9clean = p9refactor && (p9refactor.verdict === 'CLEAN' || p9refactor.passed === true || p9refactor.clean === true);
if (!p9clean) {
  return { status: 'HALTED_AT_P9', reason: 'refractor-trio did not reach grep-clean + test_tier_loader-green (I6).', p9refactor };
}
const p9content = (tier, primary, spec) =>
  preamble('9') +
  `Execute Phase 9, tiers/${tier}/ authoring. Write tiers/${tier}/{config.yaml (PINNED base-Qwen tag — ${spec}; budgets), ` +
  `prompt.txt (no-hedge voice, NO AI language I2, no Rocky I7), shell/welcome.txt, tools/tools.yaml, firstboot/setup.py ` +
  `(ensure the right base model is pulled; dead-man fallback live during the pull)}. ${primary ? 'Radagon is PRIMARY — tune ' +
  'defaults here first.' : ''} Both tiers run BASE Qwen (no fine-tune yet). Touch only tiers/${tier}/. passed iff welcome + ` +
  `prompt are AI-language-free (I2) and Rocky-free (I7) and the config loads via tier.py.`;
const [p9radagon, p9marika] = await parallel([
  () => agent(p9content('radagon', true, 'base Qwen2.5 14B (and a 7B fallback tag), full toolset'),
    { label: 'P9-radagon', phase: 'P9', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
  () => agent(p9content('marika', false, 'base Qwen2.5 3B, tighter compaction, possibly a reduced tool allowlist'),
    { label: 'P9-marika', phase: 'P9', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
]);
if (p9radagon.passed !== true || p9marika.passed !== true) {
  return { status: 'HALTED_AT_P9', reason: 'tier content authoring failed (config/prompt must load + be I2/I7-clean).', p9radagon, p9marika };
}

// ===================================================================
// FINALIZE — rollup + mossad deploy runbook. Plan stays in pending (partial buildout).
// ===================================================================
phase('Finalize: rollup + mossad deploy runbook');
const deferredAll = [...p2deferred, ...p6deferred];
const finalize = await agent(
  `All framework-core phases passed their dev-host validation (code complete + unit/mock tests green; live items deferred ` +
    `to mossad). As the FINAL step: (1) write ${AUDIT_DIR}/FINAL.md — a rollup linking each phase-<id>.md, the audit-duo ` +
    `verdicts (permissions=${p1Audit.verdict}, dispatch+dead-man=${p5Audit.verdict}), the deferred-items list ` +
    `${JSON.stringify(deferredAll)}, and the explicitly OUT-OF-SCOPE items (P7 RAG, P10 training/fine-tune, P11 installer/` +
    `ISO/shipping). (2) write ${REPO}/docs/deploy-mossad.md — a concrete runbook to bring the framework live on the mossad ` +
    `server (aaron@192.168.1.163, Arch + RTX 3060 Ti GPUs): install Ollama; pull base Qwen (14B and 7B for Radagon, 3B for ` +
    `Marika — note a 14B 4-bit ~9GB does NOT fit one 8GB 3060 Ti, so split across cards or pin a fitting quant); set ` +
    `ERDTREE_TIER; run python core/agent/main.py; then the smoke test (a read op runs instantly; a write op confirms; a ` +
    `destructive op needs the typed word; kill Ollama -> bash dead-man fires loudly; a raw command runs raw; English ` +
    `translates). Enumerate EVERY DEFERRED-TO-MOSSAD live validation to run there. Leave the plan in lifecycle/pending/ ` +
    `(this is a partial buildout — RAG, training, and shipping remain). Print a one-line summary and exit.`,
  { label: 'finalize', phase: 'Finalize', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);

return {
  status: 'FRAMEWORK_CORE_COMPLETE',
  auditDuos: { permissions: p1Audit.verdict, dispatchDeadman: p5Audit.verdict },
  deferred: deferredAll,
  outOfScope: ['P7 RAG', 'P10 training/fine-tune', 'P11 installer/ISO/shipping'],
  deployRunbook: `${REPO}/docs/deploy-mossad.md`,
  finalRollup: `${AUDIT_DIR}/FINAL.md`,
  planArchived: finalize.passed === true ? 'left in pending/ (partial buildout, by design)' : 'finalize step incomplete',
  nextStep: 'Deploy to mossad per docs/deploy-mossad.md, run the deferred live validations, then revisit RAG / training / shipping.',
};
