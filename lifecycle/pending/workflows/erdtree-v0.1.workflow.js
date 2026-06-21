// Erdtree v0.1 buildout — dynamic Workflow script.
// Compiled from lifecycle/pending/plans/erdtree-v0.1-buildout.txt (§12 orchestration guide).
// Encodes the DAG: P0 -> P1 -> P2 -> P3 -> P4 -> P5 -> {P6,P7} -> P9 -> P11,
//   P8 after {P4,P7}, P10 (training) a parallel non-blocking workstream off {P0,P4}.
// P0 is a HARD GATE (NO-GO/incomplete-strip => STOP). Critical safety/ship claims
//   route to the audit-duo SKILL (real fan-out). P9 core de-hardcode routes to refractor-trio.

export const meta = {
  name: 'erdtree-v0.1',
  description: 'Build Erdtree v0.1: an English-native Linux distro (local Ollama, invisible AI, hard permission seam) shipped as branded Marika (3B) + Radagon (7B-14B) ISOs. P0 gates everything; safety/ship-gate claims verified by audit-duo; P9 core de-hardcode via refractor-trio; P10 training is a non-blocking parallel workstream.',
  phases: [
    { title: 'P0: Gating Spikes — Harness, Telemetry Strip, License, Protocol', detail: 'SINGLE opus spike; egress-zero + license GO/NO-GO + frozen 0002 tool-call contract + bench seed. HARD GATE.' },
    { title: 'P1: Safety & System-Awareness Core', detail: '3-way worktree fanout: context/, permissions.py (opus keystone), audit.py. permissions+destructive corpus audit-duo verified.' },
    { title: 'P2: The Three High-Leverage Tools (services, packages, logs)', detail: 'Registry/interface frozen serially, then 3-way worktree fanout of the tools.' },
    { title: 'P3: Wire Ollama + Prompt Assembly', detail: 'SINGLE sonnet; localhost-only streaming client + prompt assembly per frozen 0002.' },
    { title: 'P4: Close the Loop + Tool-Call Reliability Benchmark + 3B Spike', detail: 'SEQUENTIAL opus integration spine; bench >=99.5% Radagon + 3B verdict; methodology audit-duo verified.' },
    { title: 'P5: The Product Shell + OS Integration + Dead-Man Fallback', detail: 'SEQUENTIAL opus; command-vs-English dispatch + loud bash dead-man; dispatch+dead-man audit-duo verified.' },
    { title: 'P6: Remaining Tools (network, firewall, users, disk, processes, hardware, files)', detail: '7-way worktree fanout; firewall/users/disk opus (lockout/data-loss blast radius).' },
    { title: 'P7: RAG as a TOOL (shared docs corpus, single-machine)', detail: '2-way fanout: corpus-build/embed/index (slice a) then retrieve+docs tool (slice b). Retriever reused by P8.' },
    { title: 'P8: Context Cycling / Compaction / Invisible Memory UX', detail: 'SEQUENTIAL opus after {P4,P7}; reuses P7 retriever for audit-log episodic memory.' },
    { title: 'P9: Tier Plumbing (Marika + Radagon) + ERDTREE_TIER', detail: 'tier.py + core/ de-hardcode via refractor-trio (grep-clean gate), then 2-way tier-content fanout.' },
    { title: 'P10: Training Pipeline [PARALLEL — does NOT block v0.1]', detail: 'Internal serial pipeline gen->clean->format->finetune->eval; opus on finetune/eval. Off critical path.' },
    { title: 'P11: Installer + Build + RPM Packaging [LAST]', detail: 'spec+common serially, then 2-way ISO build fanout; installed-image ship-gate invariants audit-duo verified.' },
  ],
};

const PLAN = '/Users/aaron_7nh0yzm/erdtree/lifecycle/pending/plans/erdtree-v0.1-buildout.txt';
const CLAUDE_MD = '/Users/aaron_7nh0yzm/erdtree/CLAUDE.md';
const PENDING = '/Users/aaron_7nh0yzm/erdtree/lifecycle/pending/plans/erdtree-v0.1-buildout.txt';
const ARCHIVE_PLAN = '/Users/aaron_7nh0yzm/erdtree/lifecycle/archive/plans/erdtree-v0.1-buildout.txt';
const AUDIT_DIR = '/Users/aaron_7nh0yzm/erdtree/lifecycle/archive/audits/erdtree-v0.1';

// Every build/verify agent reads the plan + CLAUDE.md first, threads the invariants,
// and writes its per-phase evidence to lifecycle/archive/audits/erdtree-v0.1/phase-<id>.md (§12.6).
function preamble(phaseId) {
  return (
    `Before doing anything: read ${CLAUDE_MD} (canonical product context + Load-Bearing Invariants) ` +
    `and the relevant phase section of ${PLAN}. Thread the invariants through your work: ` +
    `I1 no external runtime egress (local Ollama only), I2 no AI/LLM/model/agent language in user-facing ` +
    `strings, I3 permission gate before every write/destructive (destructive = literal-word-typed, never ` +
    `auto-confirm, never non-interactive), I4 append-only JSONL audit of every op, I5 system context always ` +
    `injected, I6 core/ never hardcodes a tier/product name (ERDTREE_TIER selects), I7 Rocky branding never ` +
    `user-visible, I8 simple ops feel instant, I9 dead-man bash fallback. ` +
    `When done, write your evidence (what you built, tests run + output, validation verdict) to ` +
    `${AUDIT_DIR}/phase-${phaseId}.md. Print a one-line summary and exit.\n\n`
  );
}

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log(`Erdtree v0.1 buildout starting. Plan: ${PLAN}`);

  // Verdict schemas the JS branches on (control flow done by JS, not prose).
  const goNoGoSchema = {
    type: 'object',
    required: ['verdict', 'egressZero', 'licenseVerdict', 'protocolFrozen', 'summary'],
    properties: {
      verdict: { type: 'string', enum: ['GO', 'NO-GO'] },
      egressZero: { type: 'boolean' },          // telemetry strip complete + zero outbound
      licenseVerdict: { type: 'string', enum: ['GO', 'NO-GO', 'CONDITIONAL'] },
      protocolFrozen: { type: 'boolean' },        // 0002 tool-call contract frozen + parseable
      blockers: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' },
    },
  };
  const auditDuoSchema = {
    type: 'object',
    required: ['verdict', 'summary'],
    properties: {
      verdict: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'UNRESOLVED-SPLIT'] },
      findings: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' },
    },
  };
  const benchSchema = {
    type: 'object',
    required: ['e2ePass', 'radagonValidityRate', 'radagonMeetsTarget', 'marikaVerdict', 'summary'],
    properties: {
      e2ePass: { type: 'boolean' },
      radagonValidityRate: { type: 'number' },             // 0..1
      radagonMeetsTarget: { type: 'boolean' },             // >= 0.995
      marikaVerdict: { type: 'string', enum: ['GO', 'HOLE'] }, // can 3B drive the loop?
      summary: { type: 'string' },
    },
  };
  const passSchema = {
    type: 'object',
    required: ['passed', 'summary'],
    properties: {
      passed: { type: 'boolean' },
      deferred: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' },
    },
  };

  // ===================================================================
  // PHASE 0 — Gating spikes. SINGLE, opus, foreground. HARD GATE.
  // ===================================================================
  phase('P0: Gating Spikes — Harness, Telemetry Strip, License, Protocol');
  const p0 = await agent(
    preamble('0') +
      `Execute Phase 0 of ${PLAN}. THE HARNESS IS ALREADY DECIDED — do NOT re-evaluate or guess. The reference ` +
      `substrate is OpenCode (MIT), with REAL source cloned at /Users/aaron_7nh0yzm/erdtree/vendor/opencode; ` +
      `Claude Code (vendor/claude-code) is an architectural BLUEPRINT only (proprietary + cloud-bound = NO-GO). ` +
      `FRAMING (critical): the PRODUCT is the Erdtree framework in core/ (context layer, tool abstraction, ` +
      `permission seam, audit, dispatch, memory) — the harness underneath is a SWAPPABLE substrate. Your job is ` +
      `to freeze the framework's interaction CONTRACT grounded in real reference source, NOT to marry OpenCode. ` +
      `Read the actual OpenCode source — do NOT invent flags, env vars, or behaviors (a prior attempt fabricated ` +
      `these and was refuted). Produce: ` +
      `(1) docs/decisions/0001-harness-selection.md — record the OpenCode-vs-Claude-Code decision + rationale; ` +
      `MIT obligations (ship the MIT notice in the ISO third-party manifest at P11; rebrand, no trademark grant ` +
      `— aligns I7); and an HONEST egress plan: enumerate OpenCode's REAL outbound calls by reading the source ` +
      `(auto-update, the models.dev model-catalog fetch, share, OTLP, plus LSP/plugin manifest fetches and ` +
      `remote AGENTS.md loads), noting which have genuine kill-switches and which do NOT (e.g. the models.dev ` +
      `fetch may use Bun native fetch with no disable flag). Because app-level stripping is INSUFFICIENT, the ` +
      `REAL I1 guarantee is a DISTRO-LEVEL network floor: the harness runs where outbound is firewall-blocked to ` +
      `everything except localhost (Ollama), enforced by firewalld/nftables (or a netns) at the OS layer ` +
      `(implemented in P5/P11), plus a baked local /etc/<tier>/models.json so no catalog fetch is needed. ` +
      `DO NOT FABRICATE a live egress proof — you cannot truly run the binary behind a monitor on this macOS ` +
      `host; the live zero-egress ASSERTION is a Linux-execution gate DEFERRED to P11 (installed-image test). ` +
      `Set egressZero=true iff the distro-level firewall-floor DESIGN is specified and sound (localhost-only), ` +
      `NOT based on any app-config run. ` +
      `(2) docs/decisions/0002-tool-call-protocol.md — FREEZE the tool-call contract anchored on the REAL files ` +
      `vendor/opencode/packages/llm/src/protocols/openai-compatible-chat.ts + openai-chat.ts, ` +
      `vendor/opencode/packages/llm/src/tool.ts + tool-runtime.ts, and Ollama's /v1/chat/completions ` +
      `function-calling format (request shape, tool_calls parse, tool-result, SSE delta assembly, malformed/` +
      `re-ask handling + the validity definition). Cite real file paths/line ranges; machine-consumed JSON ` +
      `examples must parse. Keep the contract framework-level (portable), not OpenCode-internal. ` +
      `(3) bench/README.md + ~10 seed bench/cases/ (validity-rate definition). Touch only docs/decisions/ and ` +
      `bench/. Set licenseVerdict=GO (MIT, confirmed at vendor/opencode/LICENSE). Set protocolFrozen=true only ` +
      `if 0002 is grounded in the actual source and parseable. verdict=NO-GO only if the real source contradicts ` +
      `the OpenCode/MIT decision.`,
    { label: 'P0-gating-spike', phase: 'P0', model: 'opus', agentType: 'general-purpose', schema: goNoGoSchema }
  );

  // §12.5: on license NO-GO or incomplete telemetry strip -> STOP and escalate. Do NOT fan out.
  if (p0.verdict === 'NO-GO' || p0.egressZero !== true || p0.licenseVerdict === 'NO-GO' || p0.protocolFrozen !== true) {
    log(`P0 GATE FAILED — halting before any fan-out. ${p0.summary}`);
    return {
      status: 'HALTED_AT_P0',
      reason: 'P0 gating spike did not clear (license NO-GO / incomplete telemetry strip / unfrozen protocol).',
      p0,
      escalation:
        'This reshapes the plan (per §12.5 / Q1) — a different harness or a hand-rolled loop may be required. ' +
        'Plan left in lifecycle/pending/plans/. Resolve P0 before resuming.',
    };
  }

  // Adversarial verification of the two irreversible-if-wrong P0 claims (audit-duo SKILL — real fan-out).
  const p0Audit = await workflow('audit-duo', {
    claim:
      'OpenCode is MIT-licensed and redistributable inside a commercial branded distro (verified against the ' +
      'real vendor/opencode/LICENSE), AND the I1 zero-egress guarantee rests on a SOUND DISTRO-LEVEL ' +
      'localhost-only firewall floor (firewalld/nftables) — NOT on app-config flags — with OpenCode\'s real ' +
      'outbound calls enumerated from actual source, and the live runtime assertion correctly DEFERRED to the ' +
      'installed-image test at P11. The decision docs invent no flags/behaviors and fabricate no live proof.',
    context:
      `docs/decisions/0001-harness-selection.md + the real source at /Users/aaron_7nh0yzm/erdtree/vendor/opencode. ` +
      `Verify three things adversarially: (a) the MIT license claim against vendor/opencode/LICENSE; (b) that the ` +
      `egress enumeration matches the ACTUAL source (no invented env vars/flags) and the firewall-floor design ` +
      `genuinely guarantees localhost-only at the OS layer; (c) that no fabricated live proof is presented as ` +
      `fact. These gate invariant I1 and the distro's shippability.`,
  });
  if (p0Audit.verdict !== 'CONFIRMED') {
    log(`P0 audit-duo did not confirm (${p0Audit.verdict}) — halting. ${p0Audit.summary}`);
    return {
      status: 'HALTED_AT_P0_AUDIT',
      reason: `audit-duo on P0 egress+license returned ${p0Audit.verdict} (no manufactured consensus, §12.5).`,
      p0, p0Audit,
    };
  }
  log('P0 cleared + audit-duo CONFIRMED. 0002 tool-call contract frozen; fanning out.');

  // Frozen contract text passed by reference into P3/P4/P10 (consolidation §12.2).
  const PROTO = 'the FROZEN tool-call contract in docs/decisions/0002-tool-call-protocol.md (do not re-derive it)';

  // P10 training is a PARALLEL, NON-BLOCKING workstream off {P0, P4}. Kick it off in the
  // background here (depends on 0002 now; its eval gate is checked but never blocks v0.1).
  const p10Promise = agent(
    preamble('10') +
      `Execute Phase 10 of ${PLAN} (PARALLEL workstream — does NOT block v0.1 ship). Build ` +
      `training/{generate/,clean.py,format.py,finetune.py,eval.py,README.md}. Training data MUST be MAJORITY ` +
      `agentic tool-call traces matching ${PROTO} (decision #2), NOT SO-style Q&A prose. Behavioral fine-tune ` +
      `only — NOT knowledge (decision #3; facts stay in RAG). Internal pipeline is SEQUENTIAL: generate -> ` +
      `clean/dedup -> format -> QLoRA finetune (Unsloth, Threadripper + 3x 3060 Ti; note 8GB/card means a 14B ` +
      `4-bit ~9GB does NOT fit one card — split or lower quant) -> eval. First empirically validate the ` +
      `one-LoRA-two-sizes FORK (fall back to per-size LoRAs if it doesn't transfer). SHIP GATE: beat base by ` +
      `>20% command accuracy AND >=99.5% tool-call validity on the Phase-4 benchmark; only then register a ` +
      `Modelfile. The Opus API is BUILD-TIME only (NOT a runtime call — I1 intact); state this in the runbook. ` +
      `Touch only training/. v0.1 ships on the BASE model regardless of this phase's eval outcome.`,
    { label: 'P10-training', phase: 'P10', model: 'opus', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }
  );

  // ===================================================================
  // PHASE 1 — Safety & system-awareness core. 3-way worktree fanout. opus on permissions.py.
  // ===================================================================
  phase('P1: Safety & System-Awareness Core');
  const p1Brief = (slice, extra) =>
    preamble('1') +
    `Execute Phase 1 of ${PLAN}. Your slice: ${slice}. Read §3 Phase 1 + invariants I3/I4/I5/I8. ` +
    `Touch ONLY your file(s) + its test. No tier names anywhere (I6). ${extra} ` +
    `Validation: your named test green; evidence = test output.`;
  const [p1ctx, p1perm, p1audit] = await parallel([
    () => agent(
      p1Brief(
        'core/context/{collector.py,snapshot.py,cache.py} + tests/test_snapshot.py',
        'collector reads /proc, /sys, systemctl, rpm -qa, ss etc., tolerates missing subsystems; ' +
          'snapshot is a typed object cheap to serialize into the prompt; cache is short-TTL latency-only ' +
          '(live box stays source of truth — decision #5). Validation: test_snapshot returns a populated snapshot.'
      ),
      { label: 'P1-context', phase: 'P1', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }
    ),
    () => agent(
      p1Brief(
        'core/agent/permissions.py + tests/test_permissions.py',
        'KEYSTONE: classify read/write/destructive; read=instant, write=confirm, destructive=literal-word-' +
          'typed-in-full, NEVER auto-confirm, NEVER non-interactive; default-deny on ambiguity (unknown write ' +
          'shape => write-confirm, unknown destructive shape => destructive). Explicit destructive taxonomy ' +
          '(rm -rf, mkfs, dd, partition ops, user/SSH/firewall lockout, remote reboot). Validation: ' +
          'test_permissions — read passes instantly, a curated destructive corpus is ALWAYS gated and never ' +
          'auto-confirmable, non-interactive destructive is refused (gates I3).'
      ),
      { label: 'P1-permissions', phase: 'P1', model: 'opus', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }
    ),
    () => agent(
      p1Brief(
        'core/agent/audit.py + tests/test_audit.py',
        'append-only JSONL writer (ts, tier, nl_input, translated_command, tool, args, permission_decision, ' +
          'exit_code, stdout_summary, stderr_summary, result); fsync-on-write; atomic; survives crash mid-write. ' +
          'Validation: test_audit — exactly one parseable JSONL line per op, append-only, partial-write recovery (gates I4).'
      ),
      { label: 'P1-audit', phase: 'P1', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }
    ),
  ]);

  // §12.5: P1 permissions is safety-critical — verify validation passed (retry-once is handled by the
  // resumable runtime / re-run); then route the classifier + destructive corpus to audit-duo.
  if (p1perm.passed !== true) {
    return { status: 'HALTED_AT_P1', reason: 'permissions.py validation failed (safety gate, §12.5: pause+escalate).', p1perm };
  }
  const p1Audit = await workflow('audit-duo', {
    claim:
      'core/agent/permissions.py NEVER under-gates: there is no destructive op (rm -rf, mkfs, dd, partition, ' +
      'SSH/firewall/user lockout, remote reboot, etc.) that slips through as a mere write-confirm or auto-confirms, ' +
      'and no path lets a destructive op run non-interactively.',
    context:
      `core/agent/permissions.py + tests/test_permissions.py from Phase 1 of ${PLAN}. Adversarially HUNT a ` +
      `destructive op that the classifier mis-files as write (under-gating is catastrophic on a live box, I3).`,
  });
  if (p1Audit.verdict !== 'CONFIRMED') {
    return { status: 'HALTED_AT_P1_AUDIT', reason: `permissions audit-duo returned ${p1Audit.verdict} (§12.5).`, p1Audit };
  }
  if (p1ctx.passed !== true || p1audit.passed !== true) {
    return { status: 'HALTED_AT_P1', reason: 'context/ or audit.py validation failed.', p1ctx, p1audit };
  }

  // ===================================================================
  // PHASE 2 — registry first (SEQ), then 3-way tool fanout. sonnet.
  // ===================================================================
  phase('P2: The Three High-Leverage Tools (services, packages, logs)');
  // Freeze the shared tool interface FIRST (§12.2) — single writer, no worktree race.
  const p2reg = await agent(
    preamble('2') +
      `Execute Phase 2 of ${PLAN}, the REGISTRY/INTERFACE slice ONLY. Build core/tools/__init__.py: a tool ` +
      `registry + uniform tool interface (name, args schema, per-op permission class read|write|destructive, ` +
      `execute()->structured result {exit_code,stdout,stderr,parsed summary}). This is the FROZEN shared ` +
      `contract that router.py (P4), tools.yaml (P9), and every tool (P2/P6/P7-docs) bind to — do not let any ` +
      `later sibling redefine it. Touch only core/tools/__init__.py. Validation: interface importable + a stub ` +
      `tool round-trips through it.`,
    { label: 'P2-registry', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  );
  if (p2reg.passed !== true) {
    return { status: 'HALTED_AT_P2', reason: 'tool registry/interface did not freeze cleanly; blocks all tool fanouts.', p2reg };
  }
  const TOOLIF = 'the FROZEN tool interface in core/tools/__init__.py (do not redefine it)';
  const p2ToolBrief = (name, extra) =>
    preamble('2') +
    `Execute Phase 2 of ${PLAN}. Your slice: core/tools/${name}.py against ${TOOLIF}. Route EVERY execute() ` +
    `through permissions + audit (Phase 1). Return STRUCTURED results. dnf NOT apt; SELinux-aware. ${extra} ` +
    `Touch only your tool + tests/test_tools_${name === 'services' ? 'services' : name}.py. ` +
    `Validation: test_tools_${name} green (read ops live on this box, write ops mock/dry-run in CI).`;
  const [p2svc, p2pkg, p2log] = await parallel([
    () => agent(p2ToolBrief('services', 'systemctl status/start/stop/restart/enable/logs; restart=write-confirm; mask=write.'),
      { label: 'P2-services', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
    () => agent(p2ToolBrief('packages', 'dnf install/remove/update/search/info; a remove whose transaction plan shows high blast radius (kernel/SSH) = destructive; surface the dnf transaction summary in the confirm.'),
      { label: 'P2-packages', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
    () => agent(p2ToolBrief('logs', 'journalctl + dmesg query/filter/tail/since; surface audit2allow-style hints for SELinux denials.'),
      { label: 'P2-logs', phase: 'P2', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
  ]);
  // §12.5: tool siblings — non-blocking single misses are deferred, not fatal. Record + continue.
  const p2deferred = [p2svc, p2pkg, p2log].filter((r) => r.passed !== true).map((r) => r.summary);
  if (p2deferred.length) log(`P2: deferred tool(s): ${p2deferred.join(' | ')}`);

  // ===================================================================
  // PHASE 3 — Ollama + prompt. SINGLE, sonnet. Gates P4.
  // ===================================================================
  phase('P3: Wire Ollama + Prompt Assembly');
  const p3 = await agent(
    preamble('3') +
      `Execute Phase 3 of ${PLAN}. Build core/model/ollama.py (streaming client to LOCAL Ollama via the ` +
      `OpenAI-compatible endpoint; model + base URL from tier config; PINNED tag, never :latest; ASSERT it only ` +
      `talks to localhost — gates I1) and core/agent/prompt.py (assemble: house system prompt with no-hedge ` +
      `voice and NO AI language per I2 + tier prompt + fresh injected context per I5 + input + recent history, ` +
      `in ${PROTO}; keep tier-specific text in tiers/ — stub for now until P9). Round-trip: assemble "show ` +
      `failing services", stream from base Qwen, confirm a well-formed tool call appears in the 0002 format. ` +
      `Touch only core/model/ollama.py, core/agent/prompt.py, tests/test_ollama_roundtrip.py. Validation: ` +
      `test_ollama_roundtrip yields a well-formed tool call; client egress = localhost only.`,
    { label: 'P3-ollama-prompt', phase: 'P3', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  );
  if (p3.passed !== true) {
    return { status: 'HALTED_AT_P3', reason: 'Ollama round-trip / localhost-egress validation failed; blocks the loop (P4).', p3 };
  }

  // ===================================================================
  // PHASE 4 — Close the loop + benchmark + 3B spike. SEQUENTIAL, opus. THE #1 BET.
  // ===================================================================
  phase('P4: Close the Loop + Tool-Call Reliability Benchmark + 3B Spike');
  const p4 = await agent(
    preamble('4') +
      `Execute Phase 4 of ${PLAN} — the integration spine and #1 technical bet (decision #2). Build ` +
      `core/agent/router.py (parse tool calls strictly against ${PROTO}; reject malformed calls and surface a ` +
      `re-ask path — count a bad call as a MISS, never crash), core/agent/context.py (per-turn context ` +
      `plumbing), core/agent/repl.py (read-eval-print loop), core/agent/main.py (wire collector -> prompt -> ` +
      `ollama -> router -> permissions -> tools -> audit -> back to model). Build bench/run_bench.py + ` +
      `bench/cases/*.json: the TOOL-CALL VALIDITY BENCHMARK measuring % of turns emitting a valid parseable ` +
      `tool call across services/packages/logs domains. Run on Radagon base (14B AND 7B) and the Marika 3B ` +
      `base; record validity rates. Touch only core/agent/{router,context,repl,main}.py + bench/. ` +
      `Validation: test_loop_e2e ("restart nginx" drives the full loop, gated at the write confirm, audited, ` +
      `answered in English on a base model); set radagonMeetsTarget=true iff Radagon validity >= 0.995; record ` +
      `the 3B marikaVerdict GO (drives the loop) or HOLE (cannot). Report the exact rates.`,
    { label: 'P4-loop-bench', phase: 'P4', model: 'opus', agentType: 'general-purpose', schema: benchSchema }
  );
  if (p4.e2ePass !== true) {
    return { status: 'HALTED_AT_P4', reason: 'test_loop_e2e failed — the end-to-end agent loop does not close.', p4 };
  }
  // §12.5: a Radagon rate < 99.5% does NOT block v0.1 (base-model ship is acceptable) — record loudly.
  const p4deferred = [];
  if (p4.radagonMeetsTarget !== true) {
    log(`P4: Radagon tool-call validity ${(p4.radagonValidityRate * 100).toFixed(2)}% < 99.5% — DEFERRED to P10 training (does NOT block v0.1).`);
    p4deferred.push(`Radagon validity ${(p4.radagonValidityRate * 100).toFixed(2)}% below 99.5% target (deferred to P10).`);
  }
  if (p4.marikaVerdict === 'HOLE') {
    log('P4: Marika 3B CANNOT drive the loop (HOLE) — flagged for product decision; Marika ships reduced or waits for the fine-tune.');
    p4deferred.push('Marika 3B agentic-reliability HOLE — product decision needed (Q2).');
  }
  // Verify the benchmark METHODOLOGY before trusting the number (audit-duo SKILL).
  const p4Audit = await workflow('audit-duo', {
    claim:
      'The Phase-4 tool-call validity benchmark MEASURES the 99.5% target honestly: cases are representative ' +
      'of real sysadmin turns across the tool domains, a malformed/unparseable call is correctly counted as a ' +
      'MISS (not silently dropped or re-tried into a pass), and the reported Radagon rate is reproducible.',
    context: `bench/run_bench.py + bench/cases/*.json + the reported rates from Phase 4 of ${PLAN}.`,
  });
  if (p4Audit.verdict === 'UNRESOLVED-SPLIT' || p4Audit.verdict === 'REFUTED') {
    return { status: 'HALTED_AT_P4_AUDIT', reason: `benchmark-methodology audit-duo returned ${p4Audit.verdict} (§12.5).`, p4, p4Audit };
  }

  // ===================================================================
  // PHASE 5 — Product shell + OS integration + dead-man. SEQUENTIAL, opus. CARDINAL UX+SAFETY.
  // ===================================================================
  phase('P5: The Product Shell + OS Integration + Dead-Man Fallback');
  const p5 = await agent(
    preamble('5') +
      `Execute Phase 5 of ${PLAN} (decisions #6/#7/#8). Build shell/shell.py (the LOGIN shell: command-vs-` +
      `English dispatch — already-valid command runs RAW transparently, English intent translates, NEVER ` +
      `mistranslate per SC4; ambiguous prefers safe behavior, never silently guesses; no "AI mode" to enter), ` +
      `shell/passthrough.py (the '!' raw-bash escape), shell/hooks/, os/systemd/ (units + Ollama dependency ` +
      `ordering — wait for Ollama but NEVER hang login if it never comes up), os/journald/ + os/dmesg/ ` +
      `(interceptor + watcher), os/pam/ (login hook). NON-NEGOTIABLE DEAD-MAN FALLBACK (I9, decision #7): ` +
      `shell.py's very first action is a guarded agent-start; ANY failure (crash / Ollama down / model mid-pull) ` +
      `-> exec bash automatically with a LOUD banner explaining the degraded state. A headless box must never be ` +
      `shell-less. Touch only shell/, os/, tests/test_dispatch.py, tests/test_deadman.py. Validation: ` +
      `test_dispatch has 0 mis-dispatches on the command-vs-English corpus (SC4); test_deadman — killing Ollama / ` +
      `agent crash / model mid-pull lands the user in bash with a loud banner, never shell-less (SC3/I9).`,
    { label: 'P5-shell-deadman', phase: 'P5', model: 'opus', agentType: 'general-purpose', schema: passSchema }
  );
  if (p5.passed !== true) {
    return { status: 'HALTED_AT_P5', reason: 'dispatch / dead-man validation failed (safety+UX gate, §12.5: pause+escalate).', p5 };
  }
  const p5Audit = await workflow('audit-duo', {
    claim:
      'The Phase-5 shell NEVER mis-dispatches (no input makes a raw command translate or an English intent run ' +
      'as a guessed raw command) AND there is NO failure mode (Ollama down, agent crash, model mid-pull) that ' +
      'leaves the user shell-less or with a quiet/uninformative fallback.',
    context: `shell/shell.py, shell/passthrough.py, os/, tests/test_dispatch.py, tests/test_deadman.py from Phase 5 of ${PLAN}.`,
  });
  if (p5Audit.verdict !== 'CONFIRMED') {
    return { status: 'HALTED_AT_P5_AUDIT', reason: `dispatch+dead-man audit-duo returned ${p5Audit.verdict} (§12.5).`, p5Audit };
  }

  // ===================================================================
  // PHASES 6 & 7 — fan out AFTER P5 (both depend on P2 interface + P4 loop). Concurrent.
  // P8 depends on {P4, P7}; we await P7 before P8 below.
  // ===================================================================
  phase('P6: Remaining Tools (network, firewall, users, disk, processes, hardware, files)');
  phase('P7: RAG as a TOOL (shared docs corpus, single-machine)');

  const p6ToolBrief = (name, model, extra) => ({
    name, model,
    brief:
      preamble('6') +
      `Execute Phase 6 of ${PLAN}. Your slice: core/tools/${name}.py against ${TOOLIF}. Declare per-op ` +
      `permission classes; lockout/data-loss ops = destructive — be MORE conservative than Claude Code ` +
      `(decision #6). ${extra} Touch only your tool + its slice of tests/test_tools_phase6.py. Validation: ` +
      `your test_tools_phase6 slice green (read live; write/destructive gated + audited; lockout-class requires ` +
      `the literal destructive confirmation).`,
  });
  const p6Specs = [
    p6ToolBrief('firewall', 'opus', 'firewalld — SSH-LOCKOUT risk: name the lockout risk explicitly in the confirm; strictest gate.'),
    p6ToolBrief('users', 'opus', 'user/group ops — locking the only admin is irreversible lockout; strictest gate.'),
    p6ToolBrief('disk', 'opus', 'mkfs/partition/dd = DATA LOSS; always destructive-typed.'),
    p6ToolBrief('network', 'sonnet', 'dropping the link you are on = remote lockout; treat as destructive.'),
    p6ToolBrief('processes', 'sonnet', 'kill/signal; killing critical pids is high-blast-radius.'),
    p6ToolBrief('hardware', 'sonnet', 'mostly read (lspci/lsblk/sensors).'),
    p6ToolBrief('files', 'sonnet', 'rm/chmod/chown on system paths can be destructive — classify conservatively.'),
  ];

  // P7's slice (b) depends on slice (a)'s index-format contract -> pipeline (a -> b), no barrier.
  // Run P6 fanout and the P7 pipeline concurrently via parallel().
  const [p6Results, p7Result] = await parallel([
    () => parallel(
      p6Specs.map((s) => () => agent(s.brief, {
        label: `P6-${s.name}`, phase: 'P6', model: s.model, agentType: 'general-purpose', isolation: 'worktree', schema: passSchema,
      }))
    ),
    () => pipeline(
      [
        {
          slice: 'a',
          brief:
            preamble('7') +
            `Execute Phase 7 of ${PLAN}, SLICE (a): rag/build_corpus.py + rag/embed.py + rag/index.py. Assemble ` +
            `the corpus (man pages, Arch wiki, Rocky/RHEL docs, quality-filtered SO, CVEs) -> chunks; ONE-TIME ` +
            `LOCAL embedding (no network, I1); local vector index (sqlite-vec/faiss, single-machine). TRACK ` +
            `per-source license in build_corpus.py — ship only redistributable sources OR ship the index-build ` +
            `recipe. FIRST define + emit the INDEX-FORMAT CONTRACT that slice (b) will read. Touch only rag/. ` +
            `Validation: index build runs fully offline.`,
        },
        {
          slice: 'b',
          brief:
            preamble('7') +
            `Execute Phase 7 of ${PLAN}, SLICE (b): rag/retrieve.py + core/tools/docs.py, reading the ` +
            `index-format contract produced by slice (a). retrieve() with an aggressive reranker — precision ` +
            `over recall, inject ~3 TIGHT chunks not 10 mediocre; expose as core/tools/docs.py against ${TOOLIF} ` +
            `so router dispatches it like any tool (retrieval is a TOOL the agent CALLS when it decides it needs ` +
            `it — decision #4, NOT prepended to every query). Wire a per-tier retrieval-BUDGET config knob ` +
            `(Marika tighter than Radagon; default off-path so "restart nginx" retrieves NOTHING). Touch only ` +
            `rag/retrieve.py, core/tools/docs.py, tests/test_rag_retrieve.py. Validation: test_rag_retrieve — a ` +
            `factual query returns tight chunks; a routine op triggers ZERO retrieval.`,
        },
      ],
      (item) => agent(item.brief, {
        label: `P7-slice-${item.slice}`, phase: 'P7', model: 'sonnet', agentType: 'general-purpose',
        isolation: 'worktree', schema: passSchema,
      })
    ),
  ]);

  const p6deferred = p6Specs
    .map((s, i) => ({ name: s.name, r: p6Results[i] }))
    .filter((x) => x.r.passed !== true)
    .map((x) => `P6 tool ${x.name} deferred: ${x.r.summary}`);
  if (p6deferred.length) log(`P6: deferred tool(s) (non-blocking, §12.5): ${p6deferred.join(' | ')}`);

  const p7b = Array.isArray(p7Result) ? p7Result[p7Result.length - 1] : p7Result;
  const p7ok = p7b && p7b.passed === true;
  if (!p7ok) log(`P7: RAG slice did not fully pass — episodic memory in P8 may degrade. ${p7b && p7b.summary}`);

  // ===================================================================
  // PHASE 8 — Memory/compaction UX. SEQUENTIAL, opus. Depends on {P4, P7}.
  // Reuses the P7 retriever for audit-log episodic memory (§12.2 — do NOT build a 2nd retriever).
  // ===================================================================
  phase('P8: Context Cycling / Compaction / Invisible Memory UX');
  const p8 = await agent(
    preamble('8') +
      `Execute Phase 8 of ${PLAN} (decision #5). Build core/agent/memory.py (TASK-scoped, not session-scoped, ` +
      `context; rolling compaction that KEEPS tool-call OUTCOMES and DROPS verbose raw outputs once reasoned ` +
      `over; keeps recent turns verbatim for deixis like "restart it"; compaction threshold = per-tier config ` +
      `knob) + core/context/facts.py (tiny curated per-host facts preamble). Implement EPISODIC MEMORY by ` +
      `REUSING the Phase-7 RAG retrieval engine (rag/retrieve.py) pointed at the audit JSONL — do NOT build a ` +
      `second retriever (§12.2). Design against the "amnesia moment": NEVER surface a context limit/reset, ` +
      `never say "out of context", never ask the user to re-explain something established (I2/UX). Touch only ` +
      `core/agent/memory.py, core/context/facts.py, tests/test_compaction.py. Validation: test_compaction — ` +
      `after exceeding the window across many tasks the session continues with no visible reset; a fact from 50 ` +
      `tasks ago is recalled via audit-log retrieval and answered as KNOWN; recent-turn deixis still resolves.`,
    { label: 'P8-memory', phase: 'P8', model: 'opus', agentType: 'general-purpose', schema: passSchema }
  );
  if (p8.passed !== true) {
    return { status: 'HALTED_AT_P8', reason: 'invisible-memory validation failed (an amnesia leak is the cardinal UX sin).', p8 };
  }

  // ===================================================================
  // PHASE 9 — Tier plumbing. tier.py + core/ de-hardcode via refractor-trio, then 2-way content fanout.
  // ===================================================================
  phase('P9: Tier Plumbing (Marika + Radagon) + ERDTREE_TIER');
  // The cross-cutting "pull tier strings out of core/" refactor with a grep-clean HARD GATE -> refractor-trio
  // WORKFLOW (real MAPPER/BUILDER/CHECKER fan-out; never inline-personated, never agentType:'refractor-pair').
  const p9refactor = await workflow('refractor-trio', {
    refactor:
      'Build core/agent/tier.py (reads ERDTREE_TIER, loads /etc/{tier}/config.yaml, resolves model tag, prompt ' +
      'path, tools allowlist, retrieval budget, compaction threshold) and then DE-HARDCODE core/: move every ' +
      'hardcoded tier/product name ("marika"/"radagon") and any Rocky branding out of core/ into tiers/ so ' +
      'ERDTREE_TIER selects everything at runtime (I6/I7/SC7).',
    scope: '/Users/aaron_7nh0yzm/erdtree/core + /Users/aaron_7nh0yzm/erdtree/tiers + core/agent/tier.py',
    verify:
      'grep -rEi "marika|radagon|rocky" /Users/aaron_7nh0yzm/erdtree/core returns ZERO user-facing hardcoded ' +
      'tier/product/Rocky strings, AND pytest tests/test_tier_loader.py passes (ERDTREE_TIER=marika vs radagon ' +
      'loads distinct config). Read CLAUDE.md invariants I6/I7 first.',
  });
  const p9grepClean = p9refactor && (p9refactor.verdict === 'CLEAN' || p9refactor.passed === true || p9refactor.clean === true);
  if (!p9grepClean) {
    return {
      status: 'HALTED_AT_P9',
      reason: 'refractor-trio did not reach a grep-clean + test_tier_loader-green state for core/ de-hardcode (I6/SC7).',
      p9refactor,
    };
  }
  // Tier content authoring — disjoint dirs, parallel, sonnet.
  const p9content = (tier, primary) =>
    preamble('9') +
    `Execute Phase 9 of ${PLAN}, tiers/${tier}/ authoring. Write tiers/${tier}/{config.yaml (PINNED model tag — ` +
    `${tier === 'marika' ? '3B, tighter retrieval/compaction, possibly reduced tool allowlist informed by the P4 3B verdict' : '7B/14B, fuller budgets, full toolset'}; budgets), ` +
    `prompt.txt (no-hedge voice, NO AI language I2, no Rocky I7), shell/welcome.txt, tools/tools.yaml, ` +
    `firstboot/setup.py (ensure the right model is pulled with the dead-man fallback live during the pull)}. ` +
    `${primary ? 'Radagon is PRIMARY — tune defaults here first.' : ''} Touch only tiers/${tier}/. ` +
    `Validation: welcome.txt + prompt.txt are AI-language-free (I2) and Rocky-free (I7); config loads via tier.py.`;
  const [p9marika, p9radagon] = await parallel([
    () => agent(p9content('radagon', true), { label: 'P9-radagon', phase: 'P9', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
    () => agent(p9content('marika', false), { label: 'P9-marika', phase: 'P9', model: 'sonnet', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
  ]);
  if (p9marika.passed !== true || p9radagon.passed !== true) {
    return { status: 'HALTED_AT_P9', reason: 'tier content authoring failed (config/prompt must load + be I2/I7-clean).', p9marika, p9radagon };
  }

  // ===================================================================
  // PHASE 11 — Installer + build + RPM. spec+common SEQ, then 2-way ISO fanout. LAST.
  // Ship-gate invariants verified by audit-duo.
  // ===================================================================
  phase('P11: Installer + Build + RPM Packaging');
  // §12.2: P9 finalized the config schema before P11's kickstart writes /etc/{tier}/config.yaml.
  const p11common = await agent(
    preamble('11') +
      `Execute Phase 11 of ${PLAN}, the SHARED slice ONLY: distro/rpm/erdtree-agent.spec (RPM packaging core/ + ` +
      `shell/ + os/ + rag/) and build/common.sh (Rocky 9 ISO build common). The kickstart consumes the ` +
      `FINALIZED P9 tier config schema. Touch only distro/, build/common.sh. Validation: spec lints; common.sh ` +
      `sourced cleanly. (opus reasoning on the brick-risk path is applied in the per-ISO builds.)`,
    { label: 'P11-common', phase: 'P11', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  );
  if (p11common.passed !== true) {
    return { status: 'HALTED_AT_P11', reason: 'RPM spec / common.sh did not build cleanly; blocks both ISO builds.', p11common };
  }
  const p11Build = (tier) =>
    preamble('11') +
    `Execute Phase 11 of ${PLAN} (LAST), the ${tier} ISO. Build build/build-${tier}.sh + installer/ ` +
    `(branding/, screens/, kickstart/) for ${tier}: kickstart sets shell.py as the LOGIN shell (/etc/passwd), ` +
    `installs Ollama, pulls the tier model with the DEAD-MAN bash fallback LIVE during the firstboot pull ` +
    `(I9/Phase 5 — first boot before the model is pulled must NOT be a shell-less brick), sets ERDTREE_TIER, ` +
    `lays down /etc/${tier}/config.yaml from the P9 schema. STRIP Rocky branding from ALL user-visible surfaces ` +
    `(boot splash, MOTD, package metadata — I7). ${tier === 'radagon' ? 'Radagon Ollama config must fit the 8GB-card floor: split a 14B across cards or pin a fitting quant (A1/Q5); document the hardware floor.' : ''} ` +
    `Touch only build/build-${tier}.sh, installer/. Validation: ISO installs + first-boots into the product ` +
    `shell with the model present (or pulling, bash fallback live); image grep = zero Rocky branding + zero ` +
    `AI language in user-visible surfaces; runtime egress on a freshly installed box = zero.`;
  const [p11radagon, p11marika] = await parallel([
    () => agent(p11Build('radagon'), { label: 'P11-radagon-iso', phase: 'P11', model: 'opus', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
    () => agent(p11Build('marika'), { label: 'P11-marika-iso', phase: 'P11', model: 'opus', agentType: 'general-purpose', isolation: 'worktree', schema: passSchema }),
  ]);
  if (p11radagon.passed !== true || p11marika.passed !== true) {
    return { status: 'HALTED_AT_P11', reason: 'one or both ISO builds failed validation (ship-gate, §12.5: pause+escalate).', p11radagon, p11marika };
  }
  // Final ship-gate invariants on the installed image -> audit-duo (a miss here is SHIPPED).
  const p11Audit = await workflow('audit-duo', {
    claim:
      'Both freshly-installed Erdtree ISOs satisfy the ship-gate invariants: ZERO runtime network egress (I1), ' +
      'ZERO Rocky branding in any user-visible surface (I7), ZERO AI/LLM/model/agent language in user-facing ' +
      'strings (I2), and the dead-man bash fallback fires loudly during the firstboot model-pull window (I9) so ' +
      'a first boot is never a shell-less brick.',
    context: `The installed Marika + Radagon images and the grep/egress checks from Phase 11 of ${PLAN}.`,
  });
  if (p11Audit.verdict !== 'CONFIRMED') {
    return { status: 'HALTED_AT_P11_AUDIT', reason: `ship-gate audit-duo returned ${p11Audit.verdict} (a miss is shipped, §12.5).`, p11Audit };
  }

  // P10 training is non-blocking — collect its (already-running) result for the rollup; never gate on it.
  const p10 = await p10Promise;
  const p10note = p10.passed === true
    ? 'P10 training pipeline built; eval-gate outcome recorded (v1.0 model swap is a config-tag flip once it clears).'
    : 'P10 training pipeline incomplete or eval-gate not cleared — v0.1 ships on the BASE model (by design, §12.5); P10 iterates for v1.0.';
  log(p10note);

  // ===================================================================
  // SUCCESS — archive the plan + write the FINAL.md rollup (§12.6). Final step, success-only.
  // ===================================================================
  phase('Finalize: archive plan + FINAL.md audit rollup');
  const deferredAll = [...p2deferred, ...p4deferred, ...p6deferred];
  const finalize = await agent(
    `All Erdtree v0.1 phases passed their validation and every audit-duo ship-gate CONFIRMED. As the FINAL ` +
    `step (success-only): (1) write ${AUDIT_DIR}/FINAL.md — a rollup linking each phase-<id>.md, the bench ` +
    `rates (Radagon validity ${(p4.radagonValidityRate * 100).toFixed(2)}%, Marika 3B verdict ${p4.marikaVerdict}), ` +
    `every audit-duo verdict, and the deferred-items list: ${JSON.stringify(deferredAll)} plus the P10 note: "${p10note}". ` +
    `(2) MOVE the plan file from ${PENDING} to ${ARCHIVE_PLAN} (git mv if tracked, else mv) — pending/=not-built, ` +
    `archive/=built. Print one-line summary and exit.`,
    { label: 'finalize', phase: 'P11', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
  );

  return {
    status: 'COMPLETE',
    p0: p0.summary,
    bench: { radagonValidityRate: p4.radagonValidityRate, radagonMeetsTarget: p4.radagonMeetsTarget, marikaVerdict: p4.marikaVerdict },
    auditDuos: {
      p0: p0Audit.verdict, p1Permissions: p1Audit.verdict, p4Methodology: p4Audit.verdict,
      p5DispatchDeadman: p5Audit.verdict, p11ShipGate: p11Audit.verdict,
    },
    deferred: deferredAll,
    training: p10note,
    planArchived: finalize.passed === true ? ARCHIVE_PLAN : `FAILED to archive — left at ${PENDING}`,
    finalRollup: `${AUDIT_DIR}/FINAL.md`,
  };
