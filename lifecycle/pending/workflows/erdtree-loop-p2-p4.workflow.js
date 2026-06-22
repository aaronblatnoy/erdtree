// Erdtree — continuation: P2 (tools) -> P3 (model wiring) -> P4 (agent loop).
// Builds on completed + verified P0 (decision docs incl. 0002) and P1 (context,
// audit, HARDENED permissions). Goal: a runnable `python core/agent/main.py`.
// No audit-duos here (P2-P4 are not the safety keystone; permissions already gates
// execution). Repo-root anchored, no worktree, dev-host writes / mossad validates.

export const meta = {
  name: 'erdtree-loop-p2-p4',
  description: 'Continue the Erdtree framework build: P2 tool registry + the three core tools (services, packages, logs), P3 the localhost Ollama client + prompt assembly on base Qwen, P4 the agent loop (router, repl, main, context) plus the tool-call validity benchmark harness. Builds on completed and verified P0/P1. Produces a runnable python core/agent/main.py. Dev host writes and unit-tests; live model and Linux validation are deferred to the mossad server and never fabricated.',
  phases: [
    { title: 'P2: Core Tools (services, packages, logs)', detail: 'registry frozen, then 3-way tool fanout. Linux tools; code + mocked tests on the dev host.' },
    { title: 'P3: Model Wiring (Ollama + prompt)', detail: 'localhost Ollama client + prompt assembly on base Qwen. Code + mock test; live round-trip deferred to mossad.' },
    { title: 'P4: The Agent Loop + Benchmark Harness', detail: 'router/repl/main/context close the loop + the tool-call validity benchmark harness. Code complete + unit-tested; live measurement deferred to mossad.' },
  ],
};

const REPO = '/home/aaron/erdtree';
const PLAN = REPO + '/lifecycle/pending/plans/erdtree-v0.1-buildout.txt';
const CLAUDE_MD = REPO + '/CLAUDE.md';
const AUDIT_DIR = REPO + '/lifecycle/archive/audits/erdtree-framework-core';
const PROTO = 'the frozen tool-call contract in docs/decisions/0002-tool-call-protocol.md (already written — do not re-derive it)';

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
    `"core/tools/services.py" means ${REPO}/core/tools/services.py). ` +
    `Before anything: read ${CLAUDE_MD} (canonical context + Load-Bearing Invariants) and the relevant phase of ${PLAN}. ` +
    `Completed already (do NOT rewrite): docs/decisions/0001-framework.md, docs/decisions/0002-tool-call-protocol.md, ` +
    `core/context/* (collector/snapshot/cache), core/agent/audit.py, and core/agent/permissions.py (the HARDENED safety ` +
    `keystone — import and use it; never reimplement or weaken it). ` +
    `DEV-HOST MODE: you are on a macOS host with NO Ollama, NO GPU, and NO Linux OS integration (systemctl/dnf/journalctl ` +
    `do NOT exist here). WRITE the code + unit tests; MOCK anything that needs a live model or Linux, and test against ` +
    `fixtures. NEVER fabricate a live result or benchmark number — a prior agent did and was refuted. For any validation ` +
    `that needs a running model or real Linux, WRITE the test and mark it DEFERRED-TO-MOSSAD. passed=true means code ` +
    `complete AND unit/mock tests green, live items honestly deferred. ` +
    `FRAMING: the PRODUCT is Erdtree's OWN framework in core/. Claude Code/OpenCode are INSPIRATION ONLY (never imported). ` +
    `Keep core/ harness- and model-portable; it must only ever talk to localhost Ollama (I1). Invariants: I1 localhost-only ` +
    `egress; I2 no AI/LLM/model/agent language in user-facing strings; I3 permission gate before every write/destructive; ` +
    `I4 append-only JSONL audit of every op; I5 system context always injected; I6 core/ never hardcodes a tier/product ` +
    `name; I8 simple ops feel instant. Write evidence to ${AUDIT_DIR}/phase-${phaseId}.md. Print a one-line summary and exit.\n\n`
  );
}

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log('Erdtree loop continuation (P2->P3->P4) starting on top of verified P0/P1.');

// ===================================================================
// P2 — registry first (SEQ), then 3-way tool fanout. sonnet.
// ===================================================================
phase('P2: Core Tools (services, packages, logs)');
const p2reg = await agent(
  preamble('2') +
    `Execute Phase 2, the REGISTRY slice ONLY: core/tools/__init__.py — a tool registry + uniform interface (name, args ` +
    `schema, per-op permission class via core/agent/permissions.py, execute()->structured result {exit_code, stdout, ` +
    `stderr, summary}). This is the FROZEN shared contract router.py (P4) and every tool bind to. Touch only ` +
    `core/tools/__init__.py. passed iff the interface is importable and a stub tool round-trips through it.`,
  { label: 'P2-registry', phase: 'P2: Core Tools (services, packages, logs)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (p2reg.passed !== true) {
  return { status: 'HALTED_AT_P2', reason: 'tool registry/interface did not freeze; blocks tool fanouts.', p2reg };
}
const TOOLIF = 'the frozen tool interface in core/tools/__init__.py (do not redefine it)';
const p2Brief = (name, extra) =>
  preamble('2') +
  `Execute Phase 2. Your slice: core/tools/${name}.py against ${TOOLIF}. Route EVERY execute() through ` +
  `core/agent/permissions.py + core/agent/audit.py. Return STRUCTURED results. dnf NOT apt; SELinux-aware. These are ` +
  `Linux tools — on macOS, MOCK the subprocess calls and test with fixtures (live execution deferred to mossad). ${extra} ` +
  `Touch only your tool + tests/test_tools_${name}.py. passed iff test_tools_${name} is green against mocks.`;
const [p2svc, p2pkg, p2log] = await parallel([
  () => agent(p2Brief('services', 'systemctl status/start/stop/restart/enable/logs; restart=write-confirm; mask=write.'),
    { label: 'P2-services', phase: 'P2: Core Tools (services, packages, logs)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
  () => agent(p2Brief('packages', 'dnf install/remove/update/search/info; a remove whose transaction plan removes kernel/SSH = destructive; surface the dnf transaction summary in the confirm.'),
    { label: 'P2-packages', phase: 'P2: Core Tools (services, packages, logs)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
  () => agent(p2Brief('logs', 'journalctl + dmesg query/filter/tail/since; surface audit2allow-style hints for SELinux denials.'),
    { label: 'P2-logs', phase: 'P2: Core Tools (services, packages, logs)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }),
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
    `fresh injected context per I5 from core/context + input + recent history, in ${PROTO}; tier text stubbed for now). ` +
    `DEV-HOST: there is no Ollama here — unit-test the client against a MOCK OpenAI-compatible server and ASSERT ` +
    `localhost-only; the live base-Qwen round-trip is DEFERRED-TO-MOSSAD. Touch only core/model/ollama.py, ` +
    `core/agent/prompt.py, tests/test_ollama_roundtrip.py. passed iff the mock round-trip parses a well-formed tool call ` +
    `and localhost-only is asserted.`,
  { label: 'P3-model-wiring', phase: 'P3: Model Wiring (Ollama + prompt)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (p3.passed !== true) {
  return { status: 'HALTED_AT_P3', reason: 'model wiring / prompt assembly failed.', p3, p2deferred };
}

// ===================================================================
// P4 — Close the loop + benchmark harness. SEQUENTIAL, opus.
// ===================================================================
phase('P4: The Agent Loop + Benchmark Harness');
const p4 = await agent(
  preamble('4') +
    `Execute Phase 4 — the integration spine that makes the framework RUNNABLE. Build core/agent/router.py (parse tool ` +
    `calls strictly against ${PROTO}; reject malformed calls + surface a re-ask path; count a bad call as a MISS, never ` +
    `crash), core/agent/context.py (per-turn context plumbing from core/context), core/agent/repl.py (the read-eval-print ` +
    `loop), core/agent/main.py (entrypoint wiring collector -> prompt -> ollama -> router -> permissions -> tools -> audit ` +
    `-> back to model; reads ERDTREE_TIER for config, defaults sensibly). Build bench/run_bench.py + bench/cases/*.json: ` +
    `the tool-call validity benchmark (% of turns emitting a valid, parseable tool call). DEV-HOST: the router parsing AND ` +
    `the benchmark RUNNER are fully unit-testable here against recorded/mock model outputs — do that. The LIVE validity ` +
    `measurement across base Qwen 14B/7B/3B and the live end-to-end loop are DEFERRED-TO-MOSSAD; do NOT fabricate a rate. ` +
    `Ensure main.py is actually runnable (python core/agent/main.py) and degrades gracefully if Ollama is unreachable ` +
    `(clear message, not a stack trace). Touch only core/agent/{router,context,repl,main}.py + bench/. passed iff router ` +
    `unit tests are green (valid calls parse, malformed counted as a miss), the benchmark runner executes against mock ` +
    `outputs, and main.py imports + starts without error.`,
  { label: 'P4-agent-loop', phase: 'P4: The Agent Loop + Benchmark Harness', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p4.passed !== true) {
  return { status: 'HALTED_AT_P4', reason: 'agent loop / router / benchmark harness incomplete.', p4, p2deferred };
}

return {
  status: 'LOOP_RUNNABLE',
  p2deferred,
  note: 'P2-P4 complete on the dev host. core/agent/main.py is runnable. Next: push to mossad, set up the Python env, and run the live loop + benchmark against the 14B (the first-playable smoke test). Then P5 (shell/dead-man), P6 (more tools), P8 (memory), P9 (tiers).',
};
