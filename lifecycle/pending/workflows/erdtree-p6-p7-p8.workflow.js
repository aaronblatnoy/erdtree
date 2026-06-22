// Erdtree — P6 (remaining tools + classifier bridge) + P7 (RAG-as-tool) + P8
// (invisible memory: compaction + facts + episodic) on top of the verified P0-P5 core.
//
// Plan: lifecycle/pending/plans/erdtree-p6-p7-p8.txt (supersedes §3 P6/P7/P8 of the
// v0.1 plan; P9-P11 unchanged + out of scope here).
//
// EXECUTION SHAPE (from the plan §3 + §12.1 DAG):
//
//     P6.t (×7 parallel) ──> P6.8 ─────────────────┐
//                                                   ├─(repl.py single-writer)─> P8.c ─> V (amnesia duo)
//     P7.1 ──> P7.ab (×2 parallel) ──> P8.s (×3 par)┘
//
//   * P6 and P7 are INDEPENDENT (disjoint files) and run CONCURRENTLY: the top-level
//     parallel() launches the 7 tool siblings AND the P7 chain (P7.1 then its 2
//     siblings) together, joined at one barrier.
//   * P6.8 (synthesize_command bridge + main.py imports) is SEQUENTIAL after all 7
//     tools land (single-writer on repl.py + main.py — two siblings editing repl.py
//     would collide on the Edit tool). Its correctness routes to the audit-duo WORKFLOW
//     ("find a (tool,op) that under-gates a destructive op").
//   * P8.s (memory.py / facts.py / episodic.py) is SEQUENTIAL after P7.ab (episodic
//     REUSES rag/retrieve.py — SC-P7.3) and runs as 3 disjoint parallel siblings.
//   * P8.c (the surgical repl.py memory-history edit + main.py wiring + test_compaction)
//     is the FINAL consolidation. repl.py is a SINGLE-WRITER file touched by BOTH P6.8
//     and P8.c, so they are STRICTLY SERIALIZED: P8.c only runs after P6.8 has fully
//     landed (we await both P6.8 and P8.s before launching P8.c). Its amnesia gate
//     routes to the audit-duo WORKFLOW.
//
//   The two irreversible-if-wrong gates — P6.8 UNDER-GATING (a wrong synthesized string
//   silently runs a destructive op on a live box) and P8.c SILENT AMNESIA (a context
//   leak breaks the invisible-memory illusion) — go to the audit-duo WORKFLOW (two
//   genuinely independent agents), NOT the consensus-verification-duo agentType (that
//   nests and collapses to one self-arguing context).
//
// HOST REALITY (verified on this build host — uname=Linux/Arch):
//   - pytest is NOT installed -> ALL test runs use `python3 -m unittest` (install pytest
//     ONLY if an agent chooses to and verifies it; never claim a pytest tally un-run).
//   - nmcli, ip, useradd, mkfs.ext4, ps, kill, lscpu, ollama are PRESENT; firewall-cmd
//     is ABSENT. This does NOT matter: the plan mandates that EVERY P6 tool test mocks
//     run_subprocess (the dev host lacks several of these binaries), so the tests are
//     fully runnable here regardless. The classifier gate keys off the SYNTHESIZED
//     command STRING, never a live binary — also fully testable on this host.
//   - The RAG embedder must be CPU-runnable on the tiny fixture corpus so test_rag_retrieve
//     runs offline here. The FULL corpus embed is genuinely DEFERRED-TO-MOSSAD (GPU + source
//     corpora) — that is the ONE legitimate deferral, not a dodge.
//
// PLAN LIFECYCLE: the plan file covers P6/P7/P8 but the BROADER erdtree-v0.1 buildout
// (P0-P11) is not complete (P9-P11 outstanding). Per §12.6 + the FINAL.md convention,
// this workflow records per-phase completion in the audits FINAL.md and LEAVES this plan
// in pending/ — it does NOT archive (archiving would falsely claim the whole v0.1 is done).

export const meta = {
  name: 'erdtree-p6-p7-p8',
  description: 'Compile Erdtree v0.1 P6+P7+P8 on top of the verified P0-P5 core. P6: the 7 remaining sysadmin tools (network/firewall/users/disk/processes/hardware/files) modeled on services.py, each implementing the FROZEN tool interface and self-registering, then a SEQUENTIAL consolidation that EXTENDS synthesize_command() in repl.py with a faithful dangerous-command branch per tool (the classifier-bridge keystone) + registers them in main.py + the exhaustive test_synthesize_command gate; under-gating routed to the audit-duo workflow. P7: a NEW rag/ package (corpus recipe + offline local embed + local vector index, sqlite-vec preferred over faiss, decided by measuring the fixture footprint) and a reusable rag.retrieve(query,index_path,k,max_chars)->[Chunk] engine, exposed as a READ-only docs tool (I2-clean summary "reference passages"). P8: invisible memory — TranscriptMemory (rolling compaction: recent turns verbatim for deixis, older turns keep tool OUTCOMES drop raw stdout), a per-host facts preamble, and episodic RAG that REUSES P7 rag.retrieve over /var/log/{tier}/audit.jsonl (NO second retriever) — wired via ONE surgical repl.py edit (history=[] seam ~line 237) that is backward-compatible (memory=None preserves today behavior); the amnesia gate routed to the audit-duo workflow. P6 and P7 run in PARALLEL; P8 trails P7; repl.py is a single-writer file serialized between P6.8 and P8.c. Host: Linux/Arch, pytest absent -> python3 -m unittest; tools mock run_subprocess; full corpus embed deferred-to-mossad. Plan stays in pending (P9-P11 outstanding).',
  phases: [
    { title: 'P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab', detail: 'P6: 7 tools (network/firewall/users/disk/processes/hardware/files) against the frozen interface, modeled on services.py, mocking run_subprocess, I2-clean, NO permissions/audit calls inside the tool. P7: Step1 contract (sqlite-vec vs faiss by measurement + the rag.retrieve signature + decision doc), then 2 siblings (corpus/index over fixtures; retrieve engine + docs tool). All run concurrently; joined at one barrier.' },
    { title: 'P6.8: synthesize_command bridge + main.py imports + gate test', detail: 'SEQUENTIAL after the 7 tools (single-writer repl.py/main.py). Extend synthesize_command() with one FAITHFUL dangerous-command branch per tool (mkfs/userdel/firewall-cmd --panic-on/ip link set down/rm -rf + the docs read branch); add the 7 imports to main.py; write the exhaustive test_synthesize_command asserting every (tool,op) classifies to its intended gate and the lockout/data-loss set is DESTRUCTIVE->CONFIRM_TYPED and REFUSE non-interactively.' },
    { title: 'V6: audit-duo on the P6.8 under-gating gate', detail: 'Two genuinely independent agents adversarially hunt a (tool,op) whose synthesized string UNDER-states blast radius (leaving a destructive op at the WRITE floor) or that fails to REFUSE non-interactively. Must converge to PASS.' },
    { title: 'P8.s (PARALLEL): memory.py || facts.py || episodic.py', detail: 'SEQUENTIAL after P7.ab. 3 disjoint siblings: TranscriptMemory (compaction policy), the per-host facts preamble loader, and EpisodicMemory that REUSES rag.retrieve over the audit JSONL (no second retriever). None touch repl.py.' },
    { title: 'P8.c: surgical repl.py memory wiring + main.py + test_compaction', detail: 'FINAL consolidation, serialized AFTER P6.8 (shared repl.py). Thread memory.compacted_history() into assemble() (history=[] seam), construct memory/facts/episodic in build_repl from opaque AppConfig knobs, write the test_compaction immortality/amnesia integration gate, and confirm the memory=None / facts-absent / index-absent regression defaults keep the existing suites green.' },
    { title: 'V8: audit-duo on the P8.c amnesia gate', detail: 'Two genuinely independent agents adversarially hunt an input/sequence that surfaces a context reset / re-asks an established fact / leaks amnesia language. Must converge to PASS.' },
    { title: 'F: Record per-phase completion (plan stays in pending)', detail: 'Only on full success: append the P6/P7/P8 rollup to the audits FINAL.md and LEAVE the plan in pending/ (P9-P11 of the broader v0.1 buildout are outstanding — do NOT archive).' },
  ],
};

const REPO = '/home/aaron/erdtree';
const PLAN = REPO + '/lifecycle/pending/plans/erdtree-p6-p7-p8.txt';
const CLAUDE_MD = REPO + '/CLAUDE.md';
const AUDIT_DIR = REPO + '/lifecycle/archive/audits/erdtree-v0.1';

// Build-agent result schema we branch on.
const passSchema = {
  type: 'object',
  required: ['passed', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    filesTouched: { type: 'array', items: { type: 'string' } },
    testsRun: { type: 'string', description: 'the EXACT command used to run the tests (python3 -m unittest ...) and a one-line pass/fail tally — never a guessed tally' },
    deferred: { type: 'array', items: { type: 'string' }, description: 'only genuinely environment-blocked items (e.g. full corpus embed on mossad), with the reason' },
    summary: { type: 'string' },
  },
};

// P7 Step-1 contract result — the backend choice + signature P8 binds to.
const contractSchema = {
  type: 'object',
  required: ['passed', 'backend', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    backend: { type: 'string', description: 'the chosen vector index backend (sqlite-vec or faiss) + why' },
    signature: { type: 'string', description: 'the frozen rag.retrieve(...) signature P8 episodic reuses' },
    footprint: { type: 'string', description: 'measured fixture SSD/RAM footprint + query latency' },
    escalate: { type: 'boolean', description: 'true iff BOTH backends blew the footprint budget (reshapes the index decision -> PAUSE)' },
    summary: { type: 'string' },
  },
};

// Audit-duo verdict the JS branches on (never a model deciding control flow).
const duoSchema = {
  type: 'object',
  required: ['verdict', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNRESOLVED'] },
    findings: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

// ------------------------------------------------------------------ //
// Shared preamble — repo root + canonical context + host reality + invariants. //
// ------------------------------------------------------------------ //
function preamble(phaseId) {
  return (
    `IMPORTANT — REPO ROOT: the Erdtree repo is at ${REPO}. Your shell CWD may be elsewhere, so FIRST run cd ${REPO}, ` +
    `and treat EVERY relative path below as relative to that repo root (e.g. "core/tools/disk.py" means ${REPO}/core/tools/disk.py). ` +
    `Before anything: read ${CLAUDE_MD} (canonical context + Load-Bearing Invariants) and the relevant §3 phase section of ${PLAN}.\n\n` +

    `WHAT EXISTS (completed + verified — import/use, do NOT rewrite): the P0-P5 core. The FROZEN tool interface is ` +
    `core/tools/__init__.py (ToolResult, ArgSpec, OpSpec, ToolSpec, the module-level \`registry\` singleton, and run_subprocess — ` +
    `the ONLY sanctioned way to shell out). The canonical TOOL TEMPLATE every P6 tool mirrors EXACTLY is core/tools/services.py ` +
    `(per-op functions returning ToolResult via run_subprocess; a _DISPATCH table; a ToolSpec with per-op permission_class; ` +
    `self-registration via \`registry.register(...)\`; the _maybe_selinux_hint helper). The loop is core/agent/repl.py ` +
    `(synthesize_command() builds the literal command line the hardened classifier sees; Repl.run_turn hardcodes history=[] ` +
    `~line 237). The classifier is core/agent/permissions.py (classify + ExecContext + OpClass + the Gate enum) — DO NOT ` +
    `re-implement or weaken it; P6 only SYNTHESIZES the right string so its existing logic fires. The audit JSONL schema is ` +
    `core/agent/audit.py. The I2 forbidden-term list is core/agent/prompt.py (_FORBIDDEN_AI_TERMS — the canonical filter; ` +
    `IMPORT it in I2 tests rather than re-listing terms).\n\n` +

    `HOST REALITY: this build host is LINUX (Arch). pytest is NOT installed — write tests in the stdlib unittest style and run ` +
    `them with "python3 -m unittest" (you MAY "pip install pytest" and use it, but only if you actually do and verify it; ` +
    `NEVER fabricate a tally). Several Linux binaries (firewall-cmd, etc.) are absent — that is fine: the plan REQUIRES every ` +
    `tool test to MOCK core.tools.<X>.run_subprocess (patch it) so no real process launches, and the classifier keys off the ` +
    `SYNTHESIZED command STRING not a live binary — so everything in P6/P8 is GENUINELY testable here. Do NOT mark testable ` +
    `logic "deferred". The ONLY legitimate deferral is the FULL corpus embed (P7) which needs mossad GPU + source corpora; the ` +
    `recipe + license manifest + a tiny fixture mini-index ship now and ARE tested offline on this host.\n\n` +

    `INVARIANTS (thread through every file — cite by number):\n` +
    `  I1  No external/network calls at runtime. Tools shell out via run_subprocess only; rag corpus EMBED is offline; docs.py ` +
    `      opens no socket. (test_rag_retrieve must assert no socket opened on the fixture index build.)\n` +
    `  I2  NEVER use "AI", "LLM", "model", "agent", "agentic", "inference", "ollama", "neural", "gpt", "retrieval", "embedding", ` +
    `      "machine learning" in ANY user-facing string — tool descriptions, op descriptions, ToolResult.summary, prompts, banners. ` +
    `      Speak plain Linux-operator language. ("Retrieved N reference passages." is the sanctioned docs summary — NOT "retrieved ` +
    `      N embeddings/chunks via the model".) Enforce by importing core/agent/prompt.py's _FORBIDDEN_AI_TERMS in a test.\n` +
    `  I3  Permission gate before every write/destructive op; destructive = typed word, never auto-confirmed, never non-interactive. ` +
    `      P6 satisfies this THROUGH the existing classifier (via synthesize_command) — NEVER by self-classifying in a tool, NEVER ` +
    `      by calling permissions/audit inside a tool.\n` +
    `  I4  Audit-log every op — the REPL already does this for every dispatch; P6 tools need NO audit code of their own.\n` +
    `  I6  No tier/product names (marika/radagon/radahn/starscourge) in core/. New config knobs (retrieval k/maxchars, compaction ` +
    `      threshold, facts path, corpus index) are read OPAQUELY (the way AppConfig.from_env already reads ERDTREE_*).\n` +
    `  I9  Never raise out of run_turn in a way that defeats the dead-man fallback: every new failure path degrades to a ToolResult ` +
    `      or a safe fallback string, never an exception that escapes the loop (a missing docs index -> an empty-but-valid ToolResult; ` +
    `      memory=None / facts-absent -> prior behavior).\n\n` +

    `Write evidence to ${AUDIT_DIR}/phase-${phaseId}.md (create the dir if needed). Print a one-line summary and exit.\n\n`
  );
}

// Per-tool op/permission/synthesize hints, lifted verbatim-in-spirit from the plan's
// Phase-6 op map so each sibling has its exact slice without re-reading the whole plan.
const TOOL_SLICES = {
  network: {
    model: 'sonnet',
    binaries: 'nmcli / ip',
    detail:
      'ops: show/status/connections/interfaces (READ); bring_up (WRITE: "ip link set <if> up" / "nmcli con up"); ' +
      'set_ip (WRITE: "nmcli con modify" / "ip addr add"); bring_down (DESTRUCTIVE — dropping the link you are on -> typed). ' +
      'Self-classify only as the OpSpec advisory; the REAL gate fires in P6.8 synthesize_command (NOT your job — you do NOT ' +
      'edit repl.py). SELinux hint not typically needed here.',
  },
  firewall: {
    model: 'opus',
    binaries: 'firewall-cmd',
    detail:
      'ops: list/get_zones/query (READ); add_service/add_port/remove_service/remove_port/reload (WRITE); ' +
      'set_default_zone (WRITE — remote-SSH lockout risk, the classifier raises stakes via ExecContext.remote); ' +
      'panic_on (DESTRUCTIVE: "firewall-cmd --panic-on"). HIGHEST lockout blast radius — the synthesize mapping (done in P6.8) ' +
      'must be exactly right; your job is the faithful tool + a correct per-op OpSpec class. NOTE firewall-cmd is ABSENT on this ' +
      'host -> you MUST mock run_subprocess in the test. SELinux hint where AVC denials are likely.',
  },
  users: {
    model: 'opus',
    binaries: 'useradd/usermod/passwd/userdel/gpasswd',
    detail:
      'ops: list/info (READ); add/set_shell/add_to_group (WRITE); lock (DESTRUCTIVE: "usermod -L <user>"); ' +
      'delete (DESTRUCTIVE: "userdel <user>"); remove_from_privgroup (DESTRUCTIVE: "gpasswd -d <user> wheel"). HIGH lockout ' +
      'blast radius. SELinux hint where relevant.',
  },
  disk: {
    model: 'opus',
    binaries: 'lsblk/df/mkfs/parted/mount/umount/dd/wipefs/smartctl',
    detail:
      'ops: usage/list (READ); smart (READ via smartctl); mount/unmount (WRITE); format (DESTRUCTIVE: "mkfs.<fstype> <device>"); ' +
      'partition (DESTRUCTIVE: "parted <device> ..."); wipe (DESTRUCTIVE: "wipefs -a <device>"); dd_write (DESTRUCTIVE: ' +
      '"dd if=... of=<device>"). HIGHEST data-loss blast radius. SELinux hint where relevant.',
  },
  processes: {
    model: 'sonnet',
    binaries: 'ps/top/kill/pkill/renice',
    detail:
      'ops: list/tree/top/info (READ); signal (WRITE: "kill <pid>" — BUT a kill -1 of init / kill-all -1 is DESTRUCTIVE, which ' +
      'the classifier catches via the synthesized argv in P6.8); renice (WRITE).',
  },
  hardware: {
    model: 'sonnet',
    binaries: 'lscpu/lspci/lsusb/lsblk/free/sensors/dmidecode',
    detail: 'ops: cpu/memory/pci/usb/block/sensors/summary — ALL READ. Keep it trivial; do NOT over-engineer. I2 filter + interface conformance still apply.',
  },
  files: {
    model: 'sonnet',
    binaries: 'ls/stat/cat/find/cp/mv/rm/mkdir/chmod/chown',
    detail:
      'ops: list/read/stat/find (READ); copy/move/mkdir/chmod/chown/write (WRITE); remove (WRITE normally, but ' +
      'recursive/forced or a system-path remove is DESTRUCTIVE via the classifier when P6.8 synthesizes "rm -rf <path>"). ' +
      'Clamp/validate args like services.logs does (e.g. a read line cap). SELinux hint where relevant. Most ops of any tool — ' +
      'still mechanical pattern work.',
  },
};

// ============================================================================
// Script body — agent/parallel/pipeline/phase/log/workflow are provided globals.
// ============================================================================
log('Erdtree P6+P7+P8 starting on top of the verified P0-P5 core. P6 (tools) and P7 (RAG) run in parallel; P8 trails P7; repl.py serialized between P6.8 and P8.c.');

// --------------------------------------------------------------------------- //
// PHASE BARRIER 1 — P6.t (×7) and the P7 chain (P7.1 -> P7.ab ×2) CONCURRENTLY. //
// One parallel() launches: the 7 tool thunks AND a single thunk that runs the   //
// P7 contract step then fans its 2 siblings. All join at this barrier.          //
// --------------------------------------------------------------------------- //
phase('P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab');

function toolThunk(name) {
  const slice = TOOL_SLICES[name];
  return async () =>
    agent(
      preamble('6-tool-' + name) +
        `Execute the Phase 6 TOOL slice for core/tools/${name}.py (binaries: ${slice.binaries}).\n` +
        `MODEL IT ON core/tools/services.py EXACTLY: per-op functions returning ToolResult via run_subprocess; a _DISPATCH ` +
        `table keyed by op name; a ToolSpec with per-op OpSpec(permission_class=...); self-register with ` +
        `\`from core.tools import registry; registry.register(<SPEC>)\` at import time.\n` +
        `${name}'s op + permission map: ${slice.detail}\n` +
        `STRICT RULES: (1) shell out ONLY via run_subprocess — NO psutil / pyroute2 / shutil.rmtree / direct os.* mutation; ` +
        `the classifier can only reason about the SYNTHESIZED command string, so the real op MUST go through a command vector. ` +
        `(2) NEVER call permissions or audit inside the tool (A3 — the REPL resolves the gate + writes the audit). ` +
        `(3) every ToolSpec/OpSpec description AND every ToolResult.summary must clear the I2 filter — assert this in your test ` +
        `by importing core/agent/prompt.py's _FORBIDDEN_AI_TERMS. (4) add the _maybe_selinux_hint helper (copy from services.py) ` +
        `where AVC denials are likely.\n` +
        `WRITE tests/test_tools_${name}.py (stdlib unittest): patch core.tools.${name}.run_subprocess so NO real process runs; ` +
        `assert each op returns a well-formed ToolResult, that READ ops need no gate, that the I2 filter passes on every ` +
        `description + summary, and that registry.get("${name}") is present after import. RUN it with ` +
        `"python3 -m unittest tests.test_tools_${name}" and report the exact command + tally in testsRun.\n` +
        `TOUCH ONLY core/tools/${name}.py and tests/test_tools_${name}.py. Do NOT edit repl.py or main.py (the P6.8 ` +
        `consolidation does the synthesize_command branch + the import — your tool just needs to self-register correctly). ` +
        `passed=true REQUIRES test_tools_${name} green on this host and the I2 filter clean.`,
      { label: '6-tool-' + name, phase: 'P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab', model: slice.model, agentType: 'general-purpose', schema: passSchema }
    );
}

const p7Thunk = async () => {
  // P7 Step 1 (SINGLE, contract-defining) — gate the 2 siblings on it.
  const p71 = await agent(
    preamble('7-step1-contract') +
      `Execute Phase 7 STEP 1 — the index/engine CONTRACT that the docs tool AND P8 episodic both bind to.\n` +
      `1. CHOOSE the LOCAL vector index backend by MEASUREMENT: default to sqlite-vec (single-file, server-less, ISO-friendly, ` +
      `reusable by P8 episodic — strongly preferred); fall back to faiss ONLY if sqlite-vec is disqualified by the measured ` +
      `fixture footprint/latency. Build a tiny fixture corpus (~a dozen chunks) under rag/fixtures/ and a CPU-only embed pass so ` +
      `the measurement (and later test_rag_retrieve) runs OFFLINE on this Linux host with no GPU. If BOTH sqlite-vec AND faiss ` +
      `blow the footprint budget on the fixture, set escalate=true and STOP (do not pick a third backend silently).\n` +
      `2. FREEZE the reusable signature rag.retrieve(query, index_path, k, max_chars) -> list[Chunk] — index_path is a PARAMETER ` +
      `(this is SC-P7.3: P8 episodic reuses the SAME engine with a different index_path; it must NOT need a code change). Write ` +
      `the signature + Chunk shape as a stub in rag/retrieve.py and the index format + query API stub in rag/index.py.\n` +
      `3. Decide the RERANKER posture (lean lexical+score rerank to avoid a second big-model footprint on 8GB cards — I8); record it.\n` +
      `4. Write docs/decisions/0003-vector-index.md: the chosen backend, the measured SSD/RAM footprint + latency, the rerank ` +
      `decision, and the frozen signature.\n` +
      `TOUCH ONLY rag/index.py (stub), rag/retrieve.py (signature stub), rag/__init__.py, rag/fixtures/, rag/requirements.txt ` +
      `(pinned embedder + index backend), docs/decisions/0003-vector-index.md. Do NOT edit repl.py or main.py. ` +
      `passed=true means the backend is chosen + measured, the signature is frozen, and the decision doc is written. ` +
      `Set backend, signature, footprint, escalate accordingly.`,
    { label: '7-step1-contract', phase: 'P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab', model: 'opus', agentType: 'general-purpose', schema: contractSchema }
  );
  if (p71.escalate === true) {
    return { p71, halted: 'P7_BACKEND_BUDGET', note: 'Both sqlite-vec and faiss blew the fixture footprint budget — reshapes the index decision; PAUSE + ESCALATE per §12.5.' };
  }
  if (p71.passed !== true) {
    return { p71, halted: 'P7_STEP1', note: 'P7 Step-1 contract did not land; the 2 siblings depend on the frozen signature, so they are not launched.' };
  }

  // P7 Step 2 (PARALLEL after Step 1) — corpus/index sibling || retrieve+docs sibling.
  const [p7a, p7b] = await parallel([
    async () =>
      agent(
        preamble('7-corpus-index') +
          `Execute Phase 7 sibling (a): the CORPUS + INDEX build against the Step-1 contract.\n` +
          `BACKEND (frozen in Step 1): ${p71.backend}.\n` +
          `1. rag/build_corpus.py — assemble + chunk a corpus from local man pages (man -k / mandb / /usr/share/man), Rocky/RHEL ` +
          `docs, Arch wiki dumps, license-gated Stack Overflow, CVE summaries; emit normalized chunks + a per-source license ` +
          `manifest. This is the RECIPE; the FULL corpus embed is DEFERRED-TO-MOSSAD (GPU) — record that deferral.\n` +
          `2. rag/embed.py — the one-time LOCAL offline embed (pinned model; CPU-capable on the tiny fixture for tests).\n` +
          `3. rag/index.py — build + query the chosen LOCAL index; build the fixture mini-index OFFLINE on this host.\n` +
          `4. rag/LICENSES.md — per-source redistribution verdict; DEFAULT POSTURE: ship the firstboot BUILD RECIPE, not the raw ` +
          `corpus (licensing — Arch wiki / SO). State this default explicitly.\n` +
          `5. tests/test_rag_index.py (stdlib unittest): the fixture index builds OFFLINE (assert NO socket opened — use a ` +
          `no-network shim) and round-trips a query. Run with "python3 -m unittest tests.test_rag_index"; report command + tally.\n` +
          `TOUCH ONLY rag/build_corpus.py, rag/embed.py, rag/index.py (build/query impl, honoring the Step-1 format), ` +
          `rag/LICENSES.md, rag/fixtures/, tests/test_rag_index.py. Do NOT edit rag/retrieve.py (sibling b owns it), repl.py, or ` +
          `main.py. passed=true REQUIRES test_rag_index green offline; the full corpus embed listed under deferred[].`,
        { label: '7-corpus-index', phase: 'P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
      ),
    async () =>
      agent(
        preamble('7-retrieve-docs') +
          `Execute Phase 7 sibling (b): the RETRIEVE ENGINE + the docs TOOL against the Step-1 contract.\n` +
          `SIGNATURE (frozen in Step 1 — bind to it EXACTLY): ${p71.signature}\n` +
          `1. rag/retrieve.py — implement the reusable engine: embed-query -> ANN search (overfetch ~k*5) -> rerank ` +
          `(lexical+score per the Step-1 rerank decision; CPU-only for tests) -> return ~k tight chunks within max_chars. ` +
          `Precision over recall. index_path is a PARAMETER (so P8 episodic reuses this same function with a different index — ` +
          `SC-P7.3; do NOT hardcode a single index). Offline only — open no socket.\n` +
          `2. core/tools/docs.py — the "docs" tool on the FROZEN interface (mirror services.py shape, self-register). ONE op: ` +
          `retrieve (READ — no gate friction). args: query (str, required), k (int, optional). execute() calls rag.retrieve and ` +
          `returns a ToolResult whose stdout is the joined chunks and summary is exactly "Retrieved N reference passages." ` +
          `(I2-CLEAN — NO "retrieval/embedding/model/inference/ollama"; "reference passages" is operator language). Read ` +
          `k/max_chars defaults from OPAQUE config (ERDTREE_RETRIEVAL_K / ERDTREE_RETRIEVAL_MAXCHARS) — never a tier name (I6). ` +
          `If the index path is absent/unreadable, register in a DEGRADED mode that returns an empty-but-valid ToolResult — never ` +
          `crash (I9).\n` +
          `3. tests/test_rag_retrieve.py: against rag/fixtures, a factual query returns tight relevant chunks within max_chars; an ` +
          `unrelated query returns low/zero results (not noise); the build is offline (no socket). tests/test_tools_docs.py: the ` +
          `docs tool implements + registers, its summary + description clear the I2 filter (import _FORBIDDEN_AI_TERMS), and it ` +
          `degrades cleanly when the index is absent. Run with "python3 -m unittest tests.test_rag_retrieve tests.test_tools_docs"; ` +
          `report command + tally.\n` +
          `TOUCH ONLY rag/retrieve.py, core/tools/docs.py, tests/test_rag_retrieve.py, tests/test_tools_docs.py. Do NOT edit ` +
          `repl.py (the docs synthesize_command READ branch is folded into the P6.8 repl.py pass) or main.py. passed=true REQUIRES ` +
          `both tests green offline and the I2 filter clean on the docs summary + description.`,
        { label: '7-retrieve-docs', phase: 'P6.t + P7 chain (PARALLEL): 7 tool siblings || P7.1->P7.ab', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
      ),
  ]);
  return { p71, p7a, p7b };
};

// One barrier launches all 7 tools + the whole P7 chain concurrently.
const barrier1 = await parallel([
  toolThunk('network'),
  toolThunk('firewall'),
  toolThunk('users'),
  toolThunk('disk'),
  toolThunk('processes'),
  toolThunk('hardware'),
  toolThunk('files'),
  p7Thunk,
]);

const toolResults = {
  network: barrier1[0], firewall: barrier1[1], users: barrier1[2], disk: barrier1[3],
  processes: barrier1[4], hardware: barrier1[5], files: barrier1[6],
};
const p7 = barrier1[7];

// P7 backend escalation is a hard stop (reshapes the index decision).
if (p7.halted === 'P7_BACKEND_BUDGET') {
  return { status: 'ESCALATE_P7_INDEX_BUDGET', reason: p7.note, p7, toolResults };
}
if (p7.halted) {
  return { status: 'HALTED_AT_' + p7.halted, reason: p7.note, p7, toolResults };
}

// A failed tool sibling is RETRYABLE/DEFERRABLE per §12.5 (a missing non-core tool
// degrades OFF safely) — but P6.8 still needs the 7 tools' shapes to wire correctly,
// so surface any failures and require they be resolved before consolidation.
const failedTools = Object.entries(toolResults).filter(([, r]) => r.passed !== true).map(([n]) => n);
if (failedTools.length > 0) {
  return {
    status: 'HALTED_AT_P6_TOOLS',
    reason: `Tool sibling(s) did not pass on-host: ${failedTools.join(', ')}. P6.8 synthesize_command wires every (tool,op), ` +
      `so the toolset must be complete + green before the classifier-bridge consolidation. Re-run those siblings, then resume.`,
    failedTools, toolResults, p7,
  };
}
if (p7.p7a.passed !== true || p7.p7b.passed !== true) {
  return {
    status: 'HALTED_AT_P7_SIBLINGS',
    reason: 'A P7 sibling (corpus/index or retrieve+docs) did not pass on-host. P8 episodic reuses rag.retrieve, so the engine ' +
      'must be green before P8.s; and the docs read branch is needed in the P6.8 repl.py pass.',
    p7, toolResults,
  };
}

// --------------------------------------------------------------------------- //
// P6.8 — SEQUENTIAL classifier-bridge consolidation (single-writer repl.py/main.py). //
// opus: a wrong synthesized string under-gates a destructive op on a live box.   //
// --------------------------------------------------------------------------- //
phase('P6.8: synthesize_command bridge + main.py imports + gate test');
const p68 = await agent(
  preamble('6-8-consolidation') +
    `Execute the Phase 6 CONSOLIDATION (P6.8) — the load-bearing classifier bridge. All 7 tools have landed + self-register; ` +
    `the P7 docs tool also exists. You are the SINGLE WRITER of core/agent/repl.py and core/agent/main.py for this pass.\n` +
    `1. EXTEND core/agent/repl.py synthesize_command() with ONE branch per new tool that renders the FAITHFUL command line so ` +
    `the EXISTING permissions.classify assigns the correct class. For DESTRUCTIVE ops emit the REAL dangerous form so the ` +
    `classifier ESCALATES: disk.format -> "mkfs.<fstype> <device>", disk.partition -> "parted <device> ...", disk.wipe -> ` +
    `"wipefs -a <device>", disk.dd_write -> "dd if=... of=<device>"; users.lock -> "usermod -L <user>", users.delete -> ` +
    `"userdel <user>", users.remove_from_privgroup -> "gpasswd -d <user> wheel"; firewall.panic_on -> "firewall-cmd --panic-on"; ` +
    `network.bring_down -> "ip link set <if> down"; processes.signal of a kill -1 / init -> the real "kill -1 <pid>" argv; ` +
    `files.remove recursive/forced/system-path -> "rm -rf <path>". ALSO add the docs READ branch (e.g. a clearly-read shape like ` +
    `"man -k <query>" or a read sentinel) so docs classifies READ -> ALLOW (no gate friction on a pure read).\n` +
    `   CONSERVATISM RULE (the cardinal P6 anti-sin): when a branch cannot render precisely, FALL THROUGH to the existing ` +
    `default f"{tool} {op}" (WRITE floor). NEVER emit a command that UNDER-states blast radius (e.g. "disk format sdb1" would ` +
    `wrongly stay at WRITE). Under-gating a destructive op is the one mistake that gets someone's disk wiped on a live box.\n` +
    `2. ADD the 7 P6 tool imports + the docs import to core/agent/main.py (import side-effect self-registers them). Guard the ` +
    `docs import so a missing/unreadable index degrades to "docs tool absent/degraded" rather than crashing build_repl (I9). ` +
    `Do NOT add the P8 memory/facts/episodic wiring yet — that is P8.c's pass (it will re-edit main.py AFTER you).\n` +
    `3. WRITE tests/test_synthesize_command.py (stdlib unittest) — THE GATE. For EVERY (tool, op) across all 7 new tools + docs, ` +
    `assert synthesize_command(ParsedCall(...)) -> permissions.classify(...) yields the intended OpClass/Gate. SPECIFICALLY ` +
    `assert the lockout/data-loss set (firewall.panic_on; users.lock/delete/remove_from_privgroup; disk.format/partition/wipe/ ` +
    `dd_write; network.bring_down; files.remove recursive) ALL classify DESTRUCTIVE -> CONFIRM_TYPED interactively AND REFUSE ` +
    `under a non-interactive ExecContext. Assert docs -> READ -> ALLOW. Also add a one-shot registry test: importing all tools ` +
    `yields registry.list_tools() == the full 10 (services/packages/logs + network/firewall/users/disk/processes/hardware/files) ` +
    `plus docs, and registry_schemas/advertised schemas build clean with zero I2-forbidden terms.\n` +
    `4. A grep gate: assert no P6 tool imports psutil/pyroute2 or calls shutil.rmtree / os.remove directly (run_subprocess only).\n` +
    `RUN: "python3 -m unittest tests.test_synthesize_command" PLUS the full existing suite ` +
    `(python3 -m unittest discover -s tests) to confirm NO regression in the pre-P6 loop/router/permissions/audit tests. Report ` +
    `the exact commands + tallies in testsRun.\n` +
    `TOUCH ONLY core/agent/repl.py (synthesize_command only — do NOT touch the dispatch/gate/audit path or the history=[] seam; ` +
    `that is P8.c), core/agent/main.py (imports only), tests/test_synthesize_command.py. passed=true REQUIRES the gate test ` +
    `green for all 10 tools + docs, the full suite green (no regression), and the grep gate clean.`,
  { label: '6-8-consolidation', phase: 'P6.8: synthesize_command bridge + main.py imports + gate test', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p68.passed !== true) {
  return { status: 'HALTED_AT_P6_8', reason: 'The synthesize_command classifier bridge (the keystone) did not pass on-host. Under-gating is irreversible-if-wrong; never auto-skip. Leaving the plan in pending.', p68, toolResults, p7 };
}

// --------------------------------------------------------------------------- //
// V6 — Audit-duo on the P6.8 under-gating gate. REAL fan-out (workflow).        //
// --------------------------------------------------------------------------- //
phase('V6: audit-duo on the P6.8 under-gating gate');
const duo6 = await workflow('audit-duo', {
  claim:
    'Erdtree P6.8 synthesize_command() renders a FAITHFUL command line for EVERY (tool, op) across the 7 new tools (network/' +
    'firewall/users/disk/processes/hardware/files) + the docs tool, such that the EXISTING hardened permissions.classify() ' +
    'assigns the correct class — and CRUCIALLY there is NO (tool, op) that UNDER-states blast radius (none that leaves a ' +
    'destructive op at the bare f"{tool} {op}" WRITE floor). The lockout/data-loss set (firewall.panic_on; users.lock/delete/' +
    'remove_from_privgroup; disk.format/partition/wipe/dd_write; network.bring_down; files.remove recursive) ALL classify ' +
    'DESTRUCTIVE -> CONFIRM_TYPED interactively AND REFUSE under a non-interactive ExecContext; docs classifies READ -> ALLOW. ' +
    'No P6 tool bypasses the classifier by performing the op via a Python lib (psutil/pyroute2/shutil.rmtree/os.remove) instead ' +
    'of run_subprocess.',
  context:
    'Repo ' + REPO + '. IMPORTANT CODE FIX SINCE LAST REVIEW: permissions.py was updated to add a dedicated DESTRUCTIVE rule ' +
    'for "ip link set <if> down" — look for the new block around verb == "ip" that checks for link+set+down and returns ' +
    'OpClass.DESTRUCTIVE with reason "bringing down a network interface can sever remote access". The test in ' +
    'tests/test_synthesize_command.py was also updated: network.bring_down now asserts OpClass.DESTRUCTIVE / Gate.CONFIRM_TYPED ' +
    '(not WRITE/CONFIRM). RE-READ the CURRENT permissions.py and tests/test_synthesize_command.py before rendering any verdict. ' +
    'Read core/agent/repl.py (the EXTENDED synthesize_command), core/agent/permissions.py (classify + ' +
    'OpClass + Gate + ExecContext — the gate keys off the SYNTHESIZED STRING, not the tool internals), all 7 core/tools/*.py + ' +
    'core/tools/docs.py, and tests/test_synthesize_command.py. The plan spec is §3 Phase 6 (esp. the Validation + Risks ' +
    'sections, the per-tool op/permission map, and SC-P6.2/SC-P6.3) of ' + PLAN + '. This is a Linux host with pytest ABSENT — ' +
    'RE-RUN the gate via "python3 -m unittest tests.test_synthesize_command" (do not trust the reported tally). ADVERSARIALLY ' +
    'construct a (tool, op, args) whose synthesized string UNDER-gates a destructive op (stays at WRITE when it should be ' +
    'DESTRUCTIVE), OR that fails to REFUSE non-interactively, OR a tool that performs its op WITHOUT going through ' +
    'run_subprocess (so the classifier never sees it). Report PASS only if you can construct none; FAIL with the concrete ' +
    'counter-example (tool, op, the wrong synthesized string, the gate it wrongly got) otherwise.',
  maxRounds: 3,
  schema: duoSchema,
});
if (duo6.verdict !== 'PASS') {
  return {
    status: duo6.verdict === 'UNRESOLVED' ? 'ESCALATE_UNRESOLVED_SPLIT_V6' : 'HALTED_AT_V6',
    reason: 'The P6.8 under-gating gate did not clear adversarial verification (SC-P6.2/SC-P6.3 — under-gating a destructive op ' +
      'is irreversible-if-wrong on a live box). Never auto-skipped. Leaving the plan in pending. ' +
      (duo6.verdict === 'UNRESOLVED' ? 'The two reviewers did not converge — honest unresolved split, no manufactured consensus.' : ''),
    duo6, p68, toolResults, p7,
  };
}

// --------------------------------------------------------------------------- //
// P8.s — 3 disjoint siblings (memory.py / facts.py / episodic.py), PARALLEL.    //
// Depends on P7.ab (episodic reuses rag.retrieve). None touch repl.py.          //
// --------------------------------------------------------------------------- //
phase('P8.s (PARALLEL): memory.py || facts.py || episodic.py');
const [p8mem, p8facts, p8epi] = await parallel([
  async () =>
    agent(
      preamble('8-memory') +
        `Execute Phase 8 sibling: core/agent/memory.py — TranscriptMemory (the subtle invisible-memory core).\n` +
        `Provide: record(assistant_msg, tool_result_msgs) to accumulate a turn; compacted_history(threshold) that KEEPS the ` +
        `recent K turns VERBATIM (so deixis "restart it" / "the one we just did" still resolves) and for OLDER turns KEEPS the ` +
        `tool-call OUTCOMES (the {exit_code, summary} shape the router already produces in tool_result_message, router.py ~line ` +
        `466) while DROPPING the verbose raw stdout/stderr once reasoned over. The threshold is an OPAQUE per-tier knob ` +
        `(chars/tokens) — I6, no tier name. PURE STDLIB accounting — NO model/network calls (I8).\n` +
        `WRITE tests/test_memory.py (stdlib unittest): after N synthetic turns exceeding the threshold, assert (a) the recent K ` +
        `turns are byte-identical, (b) older turns retain {exit_code, summary} but NOT raw stdout, (c) total size is under budget. ` +
        `Run with "python3 -m unittest tests.test_memory"; report command + tally.\n` +
        `TOUCH ONLY core/agent/memory.py and tests/test_memory.py. Do NOT edit repl.py (the P8.c consolidation threads this in). ` +
        `passed=true REQUIRES test_memory green with the three assertions.`,
      { label: '8-memory', phase: 'P8.s (PARALLEL): memory.py || facts.py || episodic.py', model: 'opus', agentType: 'general-purpose', schema: passSchema }
    ),
  async () =>
    agent(
      preamble('8-facts') +
        `Execute Phase 8 sibling: core/context/facts.py — the per-host facts preamble loader.\n` +
        `Load a tiny curated per-host facts file (path from OPAQUE config ERDTREE_FACTS_PATH — I6) and expose it as a preamble ` +
        `string that TurnContext.snapshot_text() can PREPEND (I5 augmentation, never replacement). An ABSENT file -> an EMPTY ` +
        `preamble, no error, no user-visible mention. The facts file is operator-curated (human-authored), not auto-written. ` +
        `Text must clear the I2 filter (no model/agent/inference/ollama).\n` +
        `Also make the small BACKWARD-COMPATIBLE thread in core/agent/context.py: TurnContext.snapshot_text() optionally ` +
        `prepends the facts preamble WHEN a facts source is supplied; with NO facts source the output is UNCHANGED (existing ` +
        `test_snapshot stays green). Keep this edit minimal + additive.\n` +
        `WRITE tests/test_facts.py (stdlib unittest): the preamble is injected when the file is present; empty + silent when ` +
        `absent; the text clears the I2 filter. Run with "python3 -m unittest tests.test_facts" AND re-run ` +
        `"python3 -m unittest tests.test_snapshot" to confirm the default path is unchanged; report commands + tallies.\n` +
        `TOUCH ONLY core/context/facts.py, core/agent/context.py (the minimal optional-prepend thread), tests/test_facts.py. ` +
        `Do NOT edit repl.py or main.py. passed=true REQUIRES test_facts green + test_snapshot still green.`,
      { label: '8-facts', phase: 'P8.s (PARALLEL): memory.py || facts.py || episodic.py', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
    ),
  async () =>
    agent(
      preamble('8-episodic') +
        `Execute Phase 8 sibling: core/agent/episodic.py — EpisodicMemory that REUSES rag/retrieve.py (Phase 7) — do NOT build a ` +
        `second retriever (SC-P7.3 is the whole point).\n` +
        `SIGNATURE you reuse (frozen in P7 Step 1): ${p7.p71.signature}\n` +
        `EpisodicMemory builds/refreshes a vector index over /var/log/{tier}/audit.jsonl (the audit path the REPL already writes; ` +
        `the audit fields nl_input/translated_command/tool/result are the episodic corpus — A5) and calls rag.retrieve with THIS ` +
        `index_path (different from the docs index_path — that difference PROVES reuse, not a fork). recall(query) -> short ` +
        `relevant past-operation snippets the prompt layer can inject so the loop answers "what did we do earlier" as KNOWING. ` +
        `Build the index incrementally from the JSONL (cheap append; rebuild on a size delta; accept eventual consistency — a ` +
        `just-written op is also still in the verbatim recent window). I2-clean throughout.\n` +
        `WRITE tests/test_episodic.py (stdlib unittest): a query matching a past AUDITED op returns it via the reused rag engine; ` +
        `assert the episodic index_path DIFFERS from the docs index_path (proves reuse, not a fork). Offline. Run with ` +
        `"python3 -m unittest tests.test_episodic"; report command + tally.\n` +
        `TOUCH ONLY core/agent/episodic.py and tests/test_episodic.py. import rag.retrieve — do NOT copy/fork it. Do NOT edit ` +
        `repl.py or main.py. passed=true REQUIRES test_episodic green and the reuse-not-fork assertion passing.`,
      { label: '8-episodic', phase: 'P8.s (PARALLEL): memory.py || facts.py || episodic.py', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
    ),
]);
const p8sFailed = [['memory', p8mem], ['facts', p8facts], ['episodic', p8epi]].filter(([, r]) => r.passed !== true).map(([n]) => n);
if (p8sFailed.length > 0) {
  return {
    status: 'HALTED_AT_P8_S',
    reason: `P8 sibling(s) did not pass on-host: ${p8sFailed.join(', ')}. The P8.c consolidation threads memory + facts + ` +
      `episodic into repl.py/main.py, so all three must be green first.`,
    p8mem, p8facts, p8epi, p68, p7,
  };
}

// --------------------------------------------------------------------------- //
// P8.c — FINAL consolidation. The surgical repl.py memory edit + main.py wiring  //
// + test_compaction. SERIALIZED AFTER P6.8 (both write repl.py) — guaranteed by  //
// the await order: P6.8 fully landed above before this runs. opus (one leak      //
// breaks the invisible-memory illusion).                                         //
// --------------------------------------------------------------------------- //
phase('P8.c: surgical repl.py memory wiring + main.py + test_compaction');
const p8c = await agent(
  preamble('8-c-consolidation') +
    `Execute the Phase 8 CONSOLIDATION (P8.c) — the surgical repl.py memory edit + main.py wiring + the amnesia integration ` +
    `gate. memory.py, facts.py (+ its context.py thread), and episodic.py have all landed + are green. You are the SINGLE ` +
    `WRITER of repl.py for this pass; P6.8 already finished its synthesize_command edit, so its work is on disk — PRESERVE it ` +
    `(read the current synthesize_command before you touch the file; do NOT revert or collide with it).\n` +
    `1. SURGICAL repl.py edit: Repl.__init__ accepts an OPTIONAL memory (TranscriptMemory) + episodic + facts source. ` +
    `run_turn uses memory.compacted_history() for the \`history\` arg of assemble(...) INSTEAD of the hardcoded history=[] ` +
    `(~line 237). Keep the edit to the \`history\` argument ONLY — do NOT touch the dispatch/gate/audit path. BACKWARD-COMPATIBLE: ` +
    `memory=None preserves TODAY's behavior EXACTLY (history stays []), so all existing repl/router/loop tests stay green. ` +
    `For episodic recall, PREFER routing it through the docs-tool engine (the loop CALLS it like any other read — keeps the ` +
    `"loop decides" property and reuses the I2-cleared surface) over an always-on internal inject.\n` +
    `2. main.py wiring: in build_repl construct TranscriptMemory + the facts source + the EpisodicMemory and pass them into ` +
    `Repl, reading the new knobs from AppConfig the SAME opaque way ERDTREE_* are read today (ERDTREE_RETRIEVAL_K, ` +
    `ERDTREE_COMPACTION_THRESHOLD, ERDTREE_FACTS_PATH, ERDTREE_CORPUS_INDEX). ALL have safe defaults: absence -> the feature ` +
    `degrades OFF (memory=None / empty facts / index-absent), never crashes build_repl (I9). PRESERVE the P6.8 tool/docs imports ` +
    `already in main.py.\n` +
    `3. WRITE tests/test_compaction.py — THE INTEGRATION KEYSTONE (the immortality/amnesia gate, SC-P8.1..SC-P8.4): a corpus of ` +
    `multi-task sessions that EXCEED the window. Assert (a) NO user-visible reset/limit/amnesia language EVER appears — reuse ` +
    `core/agent/prompt.py's _FORBIDDEN_AI_TERMS PLUS a dedicated amnesia-phrase blocklist ("context", "limit", "reset", ` +
    `"forgot", "earlier session", "no longer have"); (b) a fact established ~50 tasks ago is recalled via episodic and answered ` +
    `AS KNOWN (no re-ask, no "out of context"); (c) a recent-turn deixis ("restart it") still resolves to the right unit.\n` +
    `4. REGRESSION: run "python3 -m unittest discover -s tests" — the WHOLE suite (the new P6/P7/P8 tests + every pre-P6 suite: ` +
    `test_repl/test_router/test_permissions/test_audit/test_dispatch/test_deadman/test_tools_*/test_snapshot/test_main/etc.) must ` +
    `be green; the memory=None / facts-absent / index-absent defaults keep the built loop byte-compatible. Report the exact ` +
    `command + full tally in testsRun.\n` +
    `TOUCH ONLY core/agent/repl.py (the history-arg edit + the optional ctor params — NOT synthesize_command, NOT the gate/audit ` +
    `path), core/agent/main.py (the build_repl wiring — preserving P6.8's imports), tests/test_compaction.py. passed=true ` +
    `REQUIRES test_compaction green AND the full suite green (no regression) AND the amnesia blocklist clean.`,
  { label: '8-c-consolidation', phase: 'P8.c: surgical repl.py memory wiring + main.py + test_compaction', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (p8c.passed !== true) {
  return { status: 'HALTED_AT_P8_C', reason: 'The P8.c surgical repl.py memory edit / test_compaction / regression did not pass on-host. A silent amnesia regression is the cardinal UX sin; never auto-skip. Leaving the plan in pending.', p8c, p68, toolResults, p7 };
}

// --------------------------------------------------------------------------- //
// V8 — Audit-duo on the P8.c amnesia gate. REAL fan-out (workflow).             //
// --------------------------------------------------------------------------- //
phase('V8: audit-duo on the P8.c amnesia gate');
// NOTE: replaced the named audit-duo workflow with two explicit opus-pinned
// skeptics. Sonnet is unavailable (outage); opus gives full model control here.
// Both independently try to REFUTE the amnesia guarantees; PASS only if neither
// constructs a counter-example (and both actually produced a verdict — a null
// from a transient API error is NOT a pass).
const V8_CLAIM =
  'Erdtree P8 invisible memory NEVER surfaces an "amnesia moment": across multi-task sessions that exceed the context window, ' +
  'there is NO input/sequence that (a) makes the system show user-visible context-reset / limit / "amnesia" language (no ' +
  '"context", "limit", "reset", "forgot", "earlier session", "no longer have", and the I2 forbidden terms), (b) causes the ' +
  'system to RE-ASK or fail to recall an established fact from many tasks ago (episodic recall over the audit JSONL answers it ' +
  'AS KNOWN), or (c) breaks recent-turn deixis ("restart it" / "the one we just did"). The surgical repl.py edit is ' +
  'backward-compatible (memory=None preserves prior behavior; the existing suites stay green) and episodic reuses ' +
  'rag.retrieve (no second retriever).';
const V8_CONTEXT =
  'Repo ' + REPO + '. Read core/agent/memory.py (TranscriptMemory compaction policy), core/agent/episodic.py (reuses ' +
  'rag/retrieve.py over /var/log/{tier}/audit.jsonl), core/context/facts.py, the surgical edit in core/agent/repl.py (the ' +
  'history-arg wiring — confirm it ALSO preserved the P6.8 synthesize_command branches), core/agent/main.py (build_repl ' +
  'wiring + degrade-off defaults), and tests/test_compaction.py + tests/test_memory.py + tests/test_episodic.py. The plan spec ' +
  'is §3 Phase 8 (Validation + Risks + SC-P8.1..SC-P8.4) of ' + PLAN + '. NOTE: the project venv at ' + REPO + '/.venv has ' +
  'pytest + sqlite-vec (the real test env); bare /usr/bin/python3 does not. RE-RUN the suite with ' +
  '"' + REPO + '/.venv/bin/python -m pytest -q" OR "' + REPO + '/.venv/bin/python -m unittest discover -s tests" (do not trust ' +
  'the reported tally) and confirm NO regression. ADVERSARIALLY construct an input/sequence that surfaces a context reset, ' +
  'makes the system re-ask an established fact, leaks amnesia/I2 language, or breaks deixis; OR show the memory=None default ' +
  'changed existing behavior.';
const v8reviewer = (lens) =>
  agent(
    `You are an INDEPENDENT adversarial reviewer (lens: ${lens}). Try HARD to REFUTE this claim about the Erdtree codebase. ` +
    `Default to refuted=true if you cannot positively confirm it.\n\nCLAIM:\n${V8_CLAIM}\n\nCONTEXT:\n${V8_CONTEXT}\n\n` +
    `Actually read the files and actually run the suite from the venv. Then return your verdict: refuted=false ONLY if you ` +
    `genuinely cannot construct a counter-example; refuted=true with the concrete counter-example (the exact input/sequence ` +
    `and the offending string or behavior) otherwise.`,
    { label: `V8-${lens}`, phase: 'V8: audit-duo on the P8.c amnesia gate', model: 'opus', agentType: 'general-purpose',
      schema: { type: 'object', required: ['refuted', 'summary'],
        properties: { refuted: { type: 'boolean' },
          counterExample: { type: 'string' }, summary: { type: 'string' } } } }
  );
const [v8a, v8b] = await parallel([
  () => v8reviewer('correctness-and-regression'),
  () => v8reviewer('amnesia-and-deixis-leakage'),
]);
// A null reviewer (transient API error) must NOT count as a pass.
let duo8;
if (!v8a || !v8b) {
  duo8 = { verdict: 'UNRESOLVED', summary: 'A reviewer returned null (likely a transient API error) — not a pass.', v8a, v8b };
} else if (v8a.refuted || v8b.refuted) {
  duo8 = { verdict: 'FAIL', summary: 'At least one reviewer constructed a counter-example.', v8a, v8b };
} else {
  duo8 = { verdict: 'PASS', summary: 'Both independent opus reviewers failed to refute the amnesia guarantees.', v8a, v8b };
}
if (duo8.verdict !== 'PASS') {
  return {
    status: duo8.verdict === 'UNRESOLVED' ? 'ESCALATE_UNRESOLVED_SPLIT_V8' : 'HALTED_AT_V8',
    reason: 'The P8.c amnesia gate did not clear adversarial verification (SC-P8.1..SC-P8.4 — a surfaced context reset is the ' +
      'cardinal UX sin). Never auto-skipped. Leaving the plan in pending. ' +
      (duo8.verdict === 'UNRESOLVED' ? 'The two reviewers did not converge — honest unresolved split, no manufactured consensus.' : ''),
    duo8, p8c, p68, toolResults, p7,
  };
}

// --------------------------------------------------------------------------- //
// F — Record per-phase completion. PLAN STAYS IN pending (P9-P11 outstanding).  //
// --------------------------------------------------------------------------- //
phase('F: Record per-phase completion (plan stays in pending)');
const finalRec = await agent(
  `cd ${REPO}. Erdtree P6 + P7 + P8 have passed all gates on this Linux host: the 7 tools built + tested (each mocking ` +
    `run_subprocess), the synthesize_command classifier bridge extended + the exhaustive test_synthesize_command gate green + ` +
    `cleared adversarial audit-duo (no under-gating); the rag/ package (recipe + offline fixture index + reusable retrieve ` +
    `engine) + the docs tool built (I2-clean "reference passages"); invisible memory (TranscriptMemory + facts preamble + ` +
    `episodic reusing rag.retrieve) wired via the one surgical repl.py edit + test_compaction green + cleared adversarial ` +
    `audit-duo (no amnesia leak); the full existing suite still green (memory=None / facts-absent / index-absent defaults keep ` +
    `the loop byte-compatible).\n` +
    `1. Append a P6/P7/P8 rollup to ${AUDIT_DIR}/FINAL.md (create if missing) and write/update the per-phase evidence files ` +
    `${AUDIT_DIR}/phase-6.md, phase-7.md, phase-8.md per the §12.6 convention: list the files created (core/tools/{network,` +
    `firewall,users,disk,processes,hardware,files,docs}.py; rag/{__init__,build_corpus,embed,index,retrieve}.py + ` +
    `requirements.txt + LICENSES.md + fixtures/; core/agent/{memory,episodic}.py; core/context/facts.py; docs/decisions/` +
    `0003-vector-index.md; the new tests/test_* files), the files modified (core/agent/repl.py synthesize_command + the ` +
    `history-arg edit; core/agent/main.py imports + wiring; core/agent/context.py facts thread), the EXACT test commands + ` +
    `tallies, both audit-duo PASS verdicts, the chosen index backend, and the honestly-deferred items (the FULL corpus embed -> ` +
    `mossad GPU; live destructive-op typed-confirm on a real Rocky box; 8GB-card retrieval latency; the multi-hour immortal-` +
    `session soak).\n` +
    `2. DO NOT MOVE THE PLAN. The plan ${PLAN} covers P6/P7/P8, but the BROADER erdtree-v0.1 buildout (P0-P11) is NOT complete — ` +
    `P9 (tier plumbing), P10 (training), P11 (installer) are still outstanding. Per §12.6 + the FINAL.md convention, the plan ` +
    `REMAINS in pending/ (moving it to archive would falsely claim the whole v0.1 buildout is done). Verify the plan still ` +
    `resides in pending and state this explicitly in your summary. If a per-phase archive marker convention exists, follow it; ` +
    `otherwise record completion in FINAL.md only.\n` +
    `Print a one-line summary and exit.`,
  { label: 'F-record', phase: 'F: Record per-phase completion (plan stays in pending)', model: 'haiku', agentType: 'general-purpose',
    schema: { type: 'object', required: ['done', 'summary'], properties: { done: { type: 'boolean' }, planLocation: { type: 'string' }, summary: { type: 'string' } } } }
);

return {
  status: 'P6_P7_P8_COMPLETE',
  built: {
    P6_tools: ['network', 'firewall', 'users', 'disk', 'processes', 'hardware', 'files'].map((t) => `core/tools/${t}.py`),
    P6_bridge: 'core/agent/repl.py synthesize_command extended (faithful dangerous command per tool + docs READ branch) + main.py imports + tests/test_synthesize_command.py',
    P7_rag: ['rag/build_corpus.py', 'rag/embed.py', 'rag/index.py', 'rag/retrieve.py (the reusable engine)', 'core/tools/docs.py', 'rag/LICENSES.md', 'docs/decisions/0003-vector-index.md'],
    P7_backend: p7.p71.backend,
    P8_memory: ['core/agent/memory.py (TranscriptMemory)', 'core/context/facts.py', 'core/agent/episodic.py (reuses rag.retrieve)', 'surgical core/agent/repl.py history wiring', 'core/agent/main.py memory/facts/episodic wiring', 'tests/test_compaction.py'],
  },
  verified: 'P6.8 no-under-gating gate (SC-P6.2/SC-P6.3) + P8.c no-amnesia gate (SC-P8.1..SC-P8.4), each confirmed by an independent audit-duo. Full pre-P6 suite still green (backward-compatible defaults).',
  deferred: []
    .concat(...['network', 'firewall', 'users', 'disk', 'processes', 'hardware', 'files'].map((t) => toolResults[t].deferred || []))
    .concat(p7.p71 && p7.p71.footprint ? [] : [])
    .concat(p7.p7a.deferred || [], p7.p7b.deferred || [], p8mem.deferred || [], p8facts.deferred || [], p8epi.deferred || [], p8c.deferred || [])
    .concat(['Full corpus embed + index build -> mossad GPU (D2)', 'Live destructive-op typed-confirm on a real Rocky/SELinux box (D1)', '8GB-card retrieval latency (D3)', 'Multi-hour immortal-session soak (D4)']),
  planLocation: finalRec && finalRec.planLocation ? finalRec.planLocation : 'pending (P9-P11 of erdtree-v0.1 still outstanding — plan intentionally NOT archived)',
  note: 'Erdtree P6 (the 7 lockout/data-loss tools + the classifier bridge), P7 (RAG-as-a-tool, reusable engine), and P8 (invisible memory: compaction + facts + episodic) are built + verified on the Linux host on top of P0-P5. P6 and P7 ran concurrently; P8 trailed P7; repl.py was serialized between the P6.8 and P8.c single-writer passes. The full corpus embed is genuinely deferred-to-mossad. Next on the v0.1 critical path: P9 (tier plumbing) -> P11 (installer); P10 (training) is the parallel off-critical workstream.',
};
