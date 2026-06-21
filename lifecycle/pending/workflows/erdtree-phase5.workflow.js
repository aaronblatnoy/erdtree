// Erdtree — Phase 5: The Product Shell + OS Integration + Dead-Man's Fallback.
// Turns the verified P0-P4 agent loop (core/agent/repl.py + main.py) into the
// LOGIN SHELL: mode toggling (!! / !cmd), command-vs-English dispatch (0
// mis-dispatches is the gate), and the NON-NEGOTIABLE dead-man bash fallback (I9).
//
// EXECUTION SHAPE (from the plan, §3 Phase 5 + §12.1): [SEQUENTIAL — depends on
// P4]. shell/ and os/ are separable but the dead-man path spans BOTH, so they are
// kept coordinated (B1 shell -> B2 os), not blindly parallel. The two
// irreversible-if-wrong gates (dispatch correctness + never-shell-less) route to
// the audit-duo WORKFLOW for genuinely-independent adversarial confirmation —
// NOT the consensus-verification-duo agentType (that nests + collapses to theater).
//
// HOST REALITY (corrected from the P2-P4 workflow's macOS assumption): this build
// host is LINUX (Arch) with bash, systemctl, and ollama PRESENT. So unlike the
// model/Linux-tool phases, Phase 5's shell logic is GENUINELY testable here:
//   - dispatch.py uses shutil.which against the real PATH -> real test corpus.
//   - the dead-man exec_bash path can be exercised in a child process.
// There is no "DEFERRED-TO-MOSSAD" dodge for the shell logic itself. The ONLY
// deferred items are live systemd UNIT activation + PAM login wiring (those need a
// provisioned Rocky box + root + /etc/passwd edits, done at install — Phase 11);
// the unit/conf/pam FILES are authored and statically validated here.
//
// PRE-EXISTING DRAFTS (on disk already — VERIFY + COMPLETE, do NOT rewrite from
// scratch unless a draft is wrong): shell/__init__.py, shell/dispatch.py,
// shell/prompt.py, shell/passthrough.py, shell/hooks/__init__.py,
// shell/hooks/startup.py. MISSING (must be created): shell/shell.py,
// os/systemd/erdtree-agent.service, os/journald/erdtree.conf, os/pam/erdtree,
// tests/test_dispatch.py, tests/test_deadman.py.

export const meta = {
  name: 'erdtree-phase5',
  description: 'Compile Phase 5 of the Erdtree v0.1 buildout: turn the verified P0-P4 agent loop into the LOGIN SHELL. Complete + verify the pre-existing shell/ drafts (dispatch, prompt, passthrough, hooks), build the missing shell/shell.py (mode state + input loop + dead-man fallback), author the os/ integration files (systemd unit, journald conf, pam hook), and write tests/test_dispatch.py + tests/test_deadman.py. Locked UX: !! toggles NL<->BASH permanently, !cmd runs one bash command without leaving NL, colored per-tier prompts, conservative command-vs-English dispatch (0 mis-dispatches is the gate), and the NON-NEGOTIABLE loud dead-man bash fallback (I9 — never leave the user shell-less). The shell logic is REALLY tested on this Linux host (not deferred). The two irreversible gates (dispatch correctness + never-shell-less) are confirmed by the audit-duo workflow before the plan is archived.',
  phases: [
    { title: 'B1: Shell core (dispatch, prompt, passthrough, shell.py, tests)', detail: 'Verify+complete the shell/ drafts; build shell/shell.py (mode state, input loop, dead-man fallback); write test_dispatch.py + test_deadman.py and RUN them green on this Linux host.' },
    { title: 'B2: OS integration files (systemd, journald, pam)', detail: 'Author os/systemd/erdtree-agent.service (Ollama ordering + no-hang fallback), os/journald/erdtree.conf, os/pam/erdtree. Static validation here; live activation deferred to install (Phase 11).' },
    { title: 'V1: Audit-duo verification of the two non-negotiable gates', detail: 'Two genuinely independent agents adversarially hunt a mis-dispatch and a shell-less failure mode (SC4 + I9). Must converge to PASS before archive.' },
    { title: 'F: Archive plan on success', detail: 'Only when every phase passed: record evidence and move the plan pending -> archive.' },
  ],
};

const REPO = '/home/aaron/erdtree';
const PLAN = REPO + '/lifecycle/pending/plans/erdtree-v0.1-buildout.txt';
const PLAN_ARCHIVE = REPO + '/lifecycle/archive/plans/erdtree-v0.1-buildout.txt';
const CLAUDE_MD = REPO + '/CLAUDE.md';
const AUDIT_DIR = REPO + '/lifecycle/archive/audits/erdtree-v0.1';

const passSchema = {
  type: 'object',
  required: ['passed', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    testsRun: { type: 'string', description: 'the exact command used to run the tests and a one-line pass/fail tally' },
    deferred: { type: 'array', items: { type: 'string' }, description: 'only genuinely environment-blocked items (live systemd activation / PAM login), with the reason' },
    summary: { type: 'string' },
  },
};

// Audit-duo returns a verdict the JS branches on.
const duoSchema = {
  type: 'object',
  required: ['verdict', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNRESOLVED'] },
    findings: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

function preamble(phaseId) {
  return (
    `IMPORTANT — REPO ROOT: the Erdtree repo is at ${REPO}. Your shell CWD may be elsewhere, so FIRST run ` +
    `cd ${REPO}, and treat EVERY relative path below as relative to that repo root (e.g. "shell/shell.py" means ` +
    `${REPO}/shell/shell.py). Before anything: read ${CLAUDE_MD} (canonical context + Load-Bearing Invariants) and ` +
    `the §3 Phase 5 section of ${PLAN}. \n\n` +
    `WHAT EXISTS (completed + verified — import/use, do NOT rewrite): the P0-P4 agent loop. The loop being WRAPPED is ` +
    `core/agent/repl.py (class Repl, run_turn(), interactive_loop(), ConsoleIO) and core/agent/main.py (AppConfig.from_env, ` +
    `build_repl, the graceful-degrade entrypoint). Repl raises ConnectionError mid-turn when the local service is ` +
    `unreachable; main.build_repl raises at construction if the model endpoint is unreachable/misconfigured. READ BOTH ` +
    `before writing shell.py — shell.py must wrap them, not reinvent the loop.\n\n` +
    `PRE-EXISTING SHELL DRAFTS (on disk — VERIFY they meet the locked spec below, COMPLETE/FIX as needed, do NOT discard ` +
    `correct work): shell/__init__.py, shell/dispatch.py, shell/prompt.py, shell/passthrough.py, shell/hooks/__init__.py, ` +
    `shell/hooks/startup.py. Read each first; only change what is wrong or missing.\n\n` +
    `HOST REALITY: this build host is LINUX (Arch) with bash, systemctl, and ollama PRESENT, so the SHELL LOGIC IS ` +
    `GENUINELY TESTABLE HERE — actually run the tests, do NOT mark shell logic "deferred". NOTE: pytest may not be ` +
    `installed — write tests in the stdlib unittest style and run them with "python3 -m unittest" (or "python3 -m pytest" ` +
    `only if available). NEVER fabricate a test result. The ONLY legitimately deferred items are live systemd-unit ` +
    `ACTIVATION and PAM LOGIN wiring (need a provisioned Rocky box + root + /etc/passwd edits — that is install/Phase 11); ` +
    `the unit/conf/pam FILES themselves are authored and statically validated here.\n\n` +
    `LOCKED UX (implement EXACTLY — these are binding design decisions, not suggestions):\n` +
    `  MODE TOGGLING: "!!" toggles between NL mode and BASH mode PERMANENTLY (persists until toggled back). "!cmd" runs a ` +
    `  SINGLE bash command WITHOUT leaving NL mode.\n` +
    `  PROMPTS: NL mode = "[NL] ❯ " in the tier color; BASH mode = "[BASH] $ " in pink/magenta (\\033[38;5;213m) for ALL ` +
    `  tiers. NL tier colors: marika gold \\033[38;5;214m, radagon red \\033[38;5;196m, radahn deep-red \\033[38;5;124m, ` +
    `  starscourge purple \\033[38;5;93m.\n` +
    `  DISPATCH (CONSERVATIVE — 0 mis-dispatches is the gate, SC4): (1) first token starts with /, ./, ../ -> raw command; ` +
    `  (2) first token NOT on PATH -> English intent; (3) first token on PATH AND a flag token (starts with "-") present -> ` +
    `  raw; (4) first token on PATH AND a path arg (contains "/") present -> raw; (5) otherwise -> English (safe default). ` +
    `  A false-English is a minor annoyance (agent handles it); a false-RAW on a live box is the cardinal sin — never guess ` +
    `  toward raw.\n` +
    `  DEAD-MAN FALLBACK (I9 — NON-NEGOTIABLE): on STARTUP if Ollama is unreachable / times out / model not loaded -> exec ` +
    `  bash with a plain LOUD message. MID-SESSION on a ConnectionError during a turn -> exec bash with a plain message. ` +
    `  NEVER leave the user shell-less. The fallback must be the OUTERMOST guard around agent start AND around each turn.\n\n` +
    `INVARIANTS (thread through every file): I1 the shell opens NO network connections itself (only the wrapped loop talks ` +
    `to localhost Ollama). I2 NEVER use the words "AI", "LLM", "model", "agent", or "agentic" in ANY user-facing string ` +
    `(prompts, banners, fallback messages) — speak plain Linux-operator language. I6 NO tier names (marika/radagon/radahn/` +
    `starscourge) hardcoded in shell/ LOGIC — the tier label + its color are passed IN from outside (a color lookup table ` +
    `keyed by an opaque label is fine; branching shell behavior on a literal tier name is not). I7 no "Rocky" in any ` +
    `user-facing string.\n\n` +
    `Write evidence to ${AUDIT_DIR}/phase-5-${phaseId}.md (create the dir if needed). Print a one-line summary and exit.\n\n`
  );
}

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log('Erdtree Phase 5 (product shell + os integration + dead-man fallback) starting on top of verified P0-P4.');

// ===================================================================
// B1 — Shell core: complete the drafts + shell.py + the two test files.
// SEQUENTIAL keystone. opus (dispatch + dead-man are correctness-critical).
// ===================================================================
phase('B1: Shell core (dispatch, prompt, passthrough, shell.py, tests)');
const b1 = await agent(
  preamble('b1') +
    `Execute the SHELL-CORE slice of Phase 5.\n` +
    `1. VERIFY + COMPLETE the existing drafts against the LOCKED UX above: shell/dispatch.py (the 5-rule command-vs-English ` +
    `heuristic + "!!" TOGGLE signal + "!cmd" single raw), shell/prompt.py (the exact prompt strings + per-tier colors, ` +
    `opaque tier label — I6), shell/passthrough.py (run one bash command streaming output; provide the exec-into-bash ` +
    `dead-man path), shell/hooks/startup.py (pre-shell health check that decides reachable vs fall-back). Fix anything that ` +
    `deviates from the spec; keep correct code.\n` +
    `2. BUILD shell/shell.py — the main login shell. It must: hold MODE STATE (NL default, BASH after "!!", back on "!!"); ` +
    `run the input loop reading a line, rendering the right colored prompt for the current mode (shell/prompt.py); in BASH ` +
    `mode run every line as raw bash (shell/passthrough.py); in NL mode call shell/dispatch.py and act on the result ` +
    `(TOGGLE -> flip mode; RAW/"!cmd" -> one bash command, stay in NL; ENGLISH -> hand to the wrapped loop via ` +
    `core/agent/repl.Repl.run_turn / interactive single turn). The tier label + color come from OUTSIDE (env/config, ` +
    `opaque — I6), never hardcoded.\n` +
    `3. DEAD-MAN FALLBACK (I9) at the OUTERMOST layer: shell.py's first action is a GUARDED agent start (use ` +
    `shell/hooks/startup.py + core/agent/main.build_repl); ANY failure (Ollama unreachable / timeout / model not loaded / ` +
    `build_repl raises) -> exec bash with a plain LOUD banner explaining the degraded state (I2-clean: no AI/LLM/model/agent ` +
    `words). MID-SESSION: a ConnectionError raised during a turn -> exec bash with a plain message. Never an unbounded wait, ` +
    `never shell-less.\n` +
    `4. WRITE tests/test_dispatch.py — stdlib unittest. MUST cover, with 0 mis-dispatches: raw-with-flags (df -h; ls -la ` +
    `/tmp; systemctl status nginx; grep -r foo /etc), raw-with-path (cat /etc/fstab), single-word on PATH (pwd; whoami), ` +
    `English-not-on-PATH (show me failing services; why is nginx not starting), "!cmd" prefix -> always raw bash, "!!" -> ` +
    `returns the toggle signal. (Note: some of these depend on PATH; pick assertions that hold on this host — e.g. df/ls/` +
    `grep/cat/pwd/whoami exist here; if a corpus command is NOT on this host's PATH, the conservative rule sends it to ` +
    `English, so either pick PATH-present commands OR monkeypatch shutil.which deterministically. Make the corpus a ` +
    `permanent regression gate, not host-flaky.)\n` +
    `5. WRITE tests/test_deadman.py — stdlib unittest. MUST cover: Ollama unreachable on STARTUP -> bash fallback fires; ` +
    `MID-SESSION ConnectionError during a turn -> bash fallback fires; the fallback/banner message contains NONE of the ` +
    `words AI/LLM/model/agent/agentic (I2) — assert this with a substring check. Exercise the exec path safely (e.g. patch ` +
    `os.execvp / run in a child process / inject a fake exec) so the test does not actually replace the test runner.\n` +
    `6. RUN both test files on THIS host and report the exact command + pass/fail tally in testsRun. ALSO run the ` +
    `existing tests/ suite (python3 -m unittest discover -s tests, or the existing convention) to confirm no regression.\n` +
    `Touch only: shell/ (dispatch, prompt, passthrough, shell.py, __init__, hooks/), tests/test_dispatch.py, ` +
    `tests/test_deadman.py. Do NOT touch core/ or os/. passed=true REQUIRES both new test files green ON THIS HOST (not ` +
    `deferred) and 0 mis-dispatches on the corpus.`,
  { label: 'B1-shell-core', phase: 'B1: Shell core (dispatch, prompt, passthrough, shell.py, tests)', model: 'opus', agentType: 'general-purpose', schema: passSchema }
);
if (b1.passed !== true) {
  return { status: 'HALTED_AT_B1', reason: 'shell core (dispatch/dead-man/tests) did not pass on-host; the dispatch + dead-man gates are safety-critical and must not be skipped.', b1 };
}

// ===================================================================
// B2 — OS integration files. SEQUENTIAL after B1 (dead-man path spans both).
// sonnet (file authoring + static validation; no novel reasoning).
// ===================================================================
phase('B2: OS integration files (systemd, journald, pam)');
const b2 = await agent(
  preamble('b2') +
    `Execute the OS-INTEGRATION slice of Phase 5. Author three files; these are CONFIG FILES, not Python.\n` +
    `1. os/systemd/erdtree-agent.service — a systemd unit relating the product shell to the LOCAL inference service. ` +
    `ORDERING: the shell should prefer the inference service to be up (After= / Wants= the ollama service), but login MUST ` +
    `NOT HANG if it never comes up — the dead-man bash fallback (shell/shell.py, B1) fires instead. So: NO hard Requires= ` +
    `that would block login, a bounded TimeoutStartSec, and a comment pointing to the in-shell dead-man fallback as the ` +
    `real safety floor. Keep all user-visible strings I2-clean (no AI/LLM/model/agent) and I7-clean (no "Rocky"). NOTE the ` +
    `login-shell wiring (/etc/passwd) is done by the installer (Phase 11), not by this unit.\n` +
    `2. os/journald/erdtree.conf — a journald drop-in for the shell's logging (sane persistence/limits). Comment the intent. ` +
    `Recall the PRODUCT's own runtime audit log is the append-only JSONL at /var/log/<tier>/audit.jsonl (separate concern) ` +
    `— do not duplicate it here.\n` +
    `3. os/pam/erdtree — a PAM stack snippet for login integration of the product shell. Conservative + commented; the ` +
    `actual activation (dropping this into /etc/pam.d and setting shell.py as the login shell) is install-time (Phase 11).\n` +
    `STATIC VALIDATION on this host where tooling exists: run "systemd-analyze verify os/systemd/erdtree-agent.service" if ` +
    `systemd-analyze is available (report the result); otherwise do a careful structural review. Mark live ACTIVATION + PAM ` +
    `LOGIN wiring as DEFERRED (install/Phase 11) with the reason — that deferral is legitimate (needs a provisioned Rocky ` +
    `box + root). Touch only os/. passed=true means the three files are authored, I2/I7-clean, and statically validated ` +
    `(with live activation honestly deferred).`,
  { label: 'B2-os-integration', phase: 'B2: OS integration files (systemd, journald, pam)', model: 'sonnet', agentType: 'general-purpose', schema: passSchema }
);
if (b2.passed !== true) {
  return { status: 'HALTED_AT_B2', reason: 'os/ integration files incomplete or failed static validation.', b1, b2 };
}

// ===================================================================
// V1 — Audit-duo on the two irreversible gates. REAL fan-out (workflow),
// NOT the consensus-verification-duo agentType.
// ===================================================================
phase('V1: Audit-duo verification of the two non-negotiable gates');
const duo = await workflow('audit-duo', {
  claim:
    'Erdtree Phase 5 shell satisfies its two non-negotiable gates: (A) the command-vs-English dispatch has ZERO ' +
    'mis-dispatches on its corpus AND, more importantly, can never silently guess a raw command from English input (a ' +
    'false-RAW on a live box is the cardinal sin) — the conservative 5-rule order and the "!!"/"!cmd" handling are correct; ' +
    'and (B) the DEAD-MAN fallback (I9) ALWAYS leaves the user with a shell: on startup when Ollama is unreachable/times ' +
    'out/model-not-loaded, AND mid-session on a ConnectionError, the shell execs bash with a LOUD plain (I2-clean: no ' +
    'AI/LLM/model/agent/agentic words) banner — there is NO reachable code path that leaves a user shell-less, and no ' +
    'unbounded wait on Ollama startup. Also confirm shell/ hardcodes no tier name (I6) and no "Rocky" (I7) in user-facing ' +
    'strings.',
  context:
    'Repo ' + REPO + '. Read shell/shell.py, shell/dispatch.py, shell/prompt.py, shell/passthrough.py, ' +
    'shell/hooks/startup.py, tests/test_dispatch.py, tests/test_deadman.py, and the wrapped loop in core/agent/repl.py ' +
    '(ConnectionError mid-turn) + core/agent/main.py (build_repl raises at construction when the endpoint is unreachable). ' +
    'The plan spec is §3 Phase 5 of ' + PLAN + '. This is a LINUX host (bash/systemctl/ollama present) so the tests are ' +
    'runnable — RE-RUN them, do not trust a reported tally. ' +
    'IMPORTANT CODE CHANGE SINCE LAST REVIEW: dispatch.py R5 was tightened. The old R5 treated any token starting with "-" ' +
    'as a flag (causing "cat -alyze this file" → RAW). The new R5 uses _is_real_flag() with regex ' +
    '^--[a-zA-Z0-9][a-zA-Z0-9-]*$|^-[a-zA-Z0-9]{1,2}$ — only short flags (≤2 chars after single dash, or --word). ' +
    'Longer single-dash tokens like -alyze, -ing, -arefully are now correctly treated as English and dispatched to ENGLISH. ' +
    'The corpus in test_dispatch.py now includes "cat -alyze this file", "find -ing solutions now", "rm -arefully delete stuff" ' +
    'all asserted as ENGLISH. Re-read the CURRENT dispatch.py and re-run the tests before rendering your verdict. ' +
    'Adversarially: (A) find ANY input that STILL mis-dispatches to RAW from English — especially with the new ≤2-char cap; ' +
    '(B) find ANY failure mode that leaves the user shell-less or hangs login. Report verdict ' +
    'PASS only if you cannot construct either; FAIL with the concrete counter-example otherwise.',
  maxRounds: 3,
  schema: duoSchema,
});
if (duo.verdict !== 'PASS' && duo.verdict !== 'PASS_WITH_CONCERNS') {
  return {
    status: duo.verdict === 'UNRESOLVED' ? 'ESCALATE_UNRESOLVED_SPLIT' : 'HALTED_AT_V1',
    reason: 'The dispatch-correctness / never-shell-less gates did not clear adversarial verification. These are ' +
      'safety/invariant-critical (SC4 + I9) and are never auto-skipped. Leaving the plan in pending/. ' +
      (duo.verdict === 'UNRESOLVED' ? 'The two reviewers did not converge — honest unresolved split, no manufactured consensus.' : ''),
    duo, b1, b2,
  };
}

// ===================================================================
// F — Archive the plan ONLY on full success.
// ===================================================================
phase('F: Archive plan on success');
const archive = await agent(
  `cd ${REPO}. Phase 5 of the Erdtree v0.1 buildout has passed all gates: shell core built + tested on-host (0 ` +
    `mis-dispatches, dead-man fallback verified), os/ integration files authored, and the two non-negotiable gates cleared ` +
    `adversarial audit-duo review.\n` +
    `1. Append a Phase-5 rollup to ${AUDIT_DIR}/FINAL.md (create if missing): list the files created (shell/shell.py, ` +
    `os/systemd/erdtree-agent.service, os/journald/erdtree.conf, os/pam/erdtree, tests/test_dispatch.py, ` +
    `tests/test_deadman.py) + completed/verified drafts, the exact test command + tally, the audit-duo PASS, and the ` +
    `honestly-deferred items (live systemd activation + PAM login wiring -> install/Phase 11).\n` +
    `2. The Erdtree lifecycle flow is self-describing: pending/plans = "not yet built", archive/plans = "built". HOWEVER the ` +
    `plan file at ${PLAN} covers ALL 12 phases (P0-P11) and Phase 5 is only ONE of them; phases 6-11 are NOT yet built. ` +
    `Therefore DO NOT move the whole plan to archive yet (that would falsely claim the entire v0.1 buildout is done). ` +
    `Instead: verify the plan still resides in pending (it should), and in your summary state explicitly that the plan ` +
    `REMAINS IN pending/ because phases 6-11 are outstanding, and that Phase 5 specifically is complete. If you find that ` +
    `convention has changed (e.g. a per-phase archive marker exists), follow it; otherwise leave the plan in pending and ` +
    `record Phase-5 completion in FINAL.md only.\n` +
    `Print a one-line summary and exit.`,
  { label: 'F-archive', phase: 'F: Archive plan on success', model: 'sonnet', agentType: 'general-purpose',
    schema: { type: 'object', required: ['done', 'summary'], properties: { done: { type: 'boolean' }, planLocation: { type: 'string' }, summary: { type: 'string' } } } }
);

return {
  status: 'PHASE_5_COMPLETE',
  built: [
    'shell/shell.py (mode state + input loop + dead-man fallback)',
    'os/systemd/erdtree-agent.service', 'os/journald/erdtree.conf', 'os/pam/erdtree',
    'tests/test_dispatch.py', 'tests/test_deadman.py',
    'verified+completed drafts: shell/dispatch.py, shell/prompt.py, shell/passthrough.py, shell/hooks/startup.py',
  ],
  verified: '0 mis-dispatches on the dispatch corpus (SC4) + dead-man fallback never shell-less (I9), confirmed by audit-duo.',
  deferred: (b2.deferred || []).concat(b1.deferred || []),
  planLocation: archive && archive.planLocation ? archive.planLocation : 'pending (phases 6-11 still outstanding — plan intentionally NOT archived)',
  note: 'Phase 5 of erdtree-v0.1 is built and verified on the Linux host. The product shell now wraps the agent loop with mode toggling, conservative dispatch, and the loud dead-man bash fallback. Live systemd activation + PAM login wiring are deferred to the installer (Phase 11). Next on the critical path: P6 (remaining tools) / P7 (RAG) / P8 (memory) -> P9 (tiers) -> P11 (installer).',
};
