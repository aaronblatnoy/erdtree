// Erdtree — permissions classifier hardening loop.
// The P1 safety keystone (core/agent/permissions.py) failed adversarial review with
// critical under-gating (destructive ops mis-classified as plain write-confirm).
// Loop: rewrite (argv-tokenized, flag-normalized, full taxonomy + regression tests)
//   -> independent audit-duo -> repeat until CONFIRMED (max 3 rounds).

export const meta = {
  name: 'erdtree-permissions-harden',
  description: 'Harden the Erdtree permission classifier (core/agent/permissions.py), the safety keystone, after an adversarial audit-duo found critical under-gating (firewall flush, split/uppercase rm -rf on system paths, SSH/critical-file clobber, mass kill, chpasswd, remote reboot all mis-classified as plain write-confirm). Rewrite with argv tokenization + flag normalization + a complete destructive taxonomy + regression tests, then re-verify with an independent audit-duo, looping until CONFIRMED.',
  phases: [
    { title: 'Harden + verify permissions classifier', detail: 'Loop: opus rewrite (argv-normalized taxonomy + regression tests) -> independent audit-duo -> repeat until CONFIRMED (max 3 rounds).' },
  ],
};

const REPO = '/home/aaron/erdtree';
const FILE = 'core/agent/permissions.py';
const TEST = 'tests/test_permissions.py';

const passSchema = {
  type: 'object',
  required: ['passed', 'summary'],
  properties: {
    passed: { type: 'boolean' },
    remaining: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

// Script body — agent/parallel/pipeline/phase/log/workflow are provided as globals.
log('Permissions hardening loop starting (rewrite -> audit-duo -> repeat until CONFIRMED).');

let findings =
  '[SEED — from the failed P1 audit-duo; BOTH independent reviewers returned FAIL]\n' +
  '- iptables -F / --flush, ip6tables -F (flush ALL firewall rules -> lockout on default-DROP): currently WRITE, must be DESTRUCTIVE.\n' +
  '- nft flush table <fam> <name> / nft delete table <...> (named ruleset): currently WRITE, must be DESTRUCTIVE (only `nft flush ruleset` was caught).\n' +
  '- kill -9 -1 / killall -9 -1 (mass kill incl. init/sshd): destructive regex is DEAD CODE (word-boundary bug on \\b-9\\b) -> falls through to WRITE. Must be DESTRUCTIVE.\n' +
  '- rm -r/-R of system paths (/etc, /home, ...) with split/uppercase/separate flags (-r -f, -fR, -Rf, -f -R, --recursive --force): escapes the single-token case-sensitive regex; root-path fallback only catches / /* ~ $HOME. Any recursive+forced delete, or recursive delete of a system path, must be DESTRUCTIVE.\n' +
  '- SSH lockout via file CLOBBER (not just `>` redirect): tee / cp / mv / dd over /etc/ssh/sshd_config -> currently WRITE. Must be DESTRUCTIVE.\n' +
  '- Clobber of other critical files (/etc/fstab, /etc/passwd, /etc/shadow, /etc/sudoers) via cp /dev/null, tee, mv, dd -> DESTRUCTIVE.\n' +
  '- chpasswd; usermod -p "" root (blank root password); usermod -L / deluser / userdel of an admin or only-admin -> DESTRUCTIVE.\n' +
  '- Remote reboot/poweroff/halt via dbus-send / busctl / systemctl reboot|poweroff|halt -> DESTRUCTIVE.\n' +
  '- truncate -s 0 /dev/sdX; mkfs.* or dd of=/dev/sdX (write to a block device) -> DESTRUCTIVE.\n' +
  'ROOT CAUSE: a regex-on-raw-string taxonomy that does NOT tokenize argv or normalize flags.\n' +
  'TEST BLINDNESS: 427 unit tests passed because DESTRUCTIVE_CORPUS only used canonical -rf/-fr/--force forms; every variant above is untested.';

let round = 0;
let verdict = 'UNVERIFIED';
let lastAudit = null;

phase('Harden + verify permissions classifier');
while (round < 3 && verdict !== 'CONFIRMED') {
  round++;

  const fix = await agent(
    `IMPORTANT — REPO ROOT: run cd ${REPO} FIRST; every relative path below is under ${REPO} (e.g. ${FILE} = ${REPO}/${FILE}). ` +
      `Read ${REPO}/CLAUDE.md (Load-Bearing Invariants, especially I3: destructive = literal-word-typed, never auto-confirm, never ` +
      `non-interactive) and the CURRENT ${FILE} + ${TEST}. ${FILE} is the SAFETY KEYSTONE and an adversarial audit found CRITICAL ` +
      `under-gating — destructive ops mis-classified as a mere yes/no write-confirm. This is round ${round}. Findings you MUST fix (ALL): ` +
      `\n${findings}\n` +
      `MANDATE: (1) RE-ARCHITECT the classifier to TOKENIZE the command into argv (e.g. shlex.split, handle sudo/env prefixes, pipes, ` +
      `&&/;/| separators — classify EACH sub-command and take the most severe) and NORMALIZE flags so combined/split/uppercase forms are ` +
      `equivalent (-rf == -fr == -r -f == -Rf == -fR == -f -R == --recursive --force). Do NOT rely on raw-string regex for flag detection. ` +
      `(2) BROADEN the DESTRUCTIVE taxonomy to cover EVERY finding above plus obvious siblings (other firewall backends, other critical ` +
      `files, other admin-lockout verbs). (3) DEFAULT-DENY: any destructive-SHAPED but unrecognized command => DESTRUCTIVE, never write. ` +
      `(4) PRESERVE the public API and the non-interactive-refusal behavior. (5) Add ALL the above cases AND their split/uppercase/clobber ` +
      `variants to ${TEST}'s destructive corpus so CI catches regressions; keep existing passing cases green. Touch ONLY ${FILE} and ` +
      `${TEST}. DEV-HOST: this is pure logic, fully testable here — RUN the tests (pytest ${TEST}) and report real results; do NOT ` +
      `fabricate. Write evidence to ${REPO}/lifecycle/archive/audits/erdtree-framework-core/phase-1-perm-harden-r${round}.md. ` +
      `passed=true iff all tests are green AND every finding above is now gated DESTRUCTIVE (typed confirmation), never write. ` +
      `Print a one-line summary and exit.`,
    { label: `perm-fix-r${round}`, phase: 'Harden + verify permissions classifier', model: 'opus', agentType: 'general-purpose', schema: passSchema }
  );

  const audit = await workflow('audit-duo', {
    claim:
      'core/agent/permissions.py NEVER under-gates. Specifically, every one of these is classified DESTRUCTIVE (requires the literal ' +
      'typed confirmation, never a plain yes/no write-confirm, and is refused non-interactively): recursive/forced rm including split ' +
      'and uppercase flag forms (-r -f, -fR, -Rf, --recursive --force) on ANY system path; firewall flush (iptables -F / --flush, ' +
      'ip6tables -F, nft flush|delete table); mass kill (kill -9 -1, killall -9 -1); SSH/critical-file lockout via CLOBBER (tee / cp / ' +
      'mv / dd over sshd_config, fstab, passwd, shadow, sudoers); admin lockout (chpasswd, usermod -p "" root, usermod -L / deluser / ' +
      'userdel of an admin); remote reboot/poweroff via dbus-send / busctl / systemctl; and mkfs / dd / truncate to a block device.',
    context:
      `${REPO}/${FILE} + ${REPO}/${TEST} (round ${round}). TOKENIZE argv yourself and adversarially HUNT any destructive op that still ` +
      `escapes to a write-confirm — be exhaustive on flag-normalization escapes (split/uppercase/combined), sudo/env prefixes, ` +
      `command chaining (&&, ;, |), and clobber/lockout variants. Under-gating on a live box is catastrophic (I3).`,
  });

  lastAudit = audit;
  verdict = (audit && audit.verdict) || 'UNVERIFIED';
  log(`Round ${round}: fix passed=${fix && fix.passed}, audit verdict=${verdict}.`);
  if (verdict === 'CONFIRMED') break;

  // Feed this round's findings into the next rewrite.
  if (audit && audit.findings) findings = JSON.stringify(audit.findings, null, 2);
  else if (audit && audit.summary) findings = audit.summary;
}

return {
  status: verdict === 'CONFIRMED' ? 'PERMISSIONS_HARDENED' : 'PERMISSIONS_STILL_FAILING',
  rounds: round,
  verdict,
  auditSummary: lastAudit && lastAudit.summary,
  nextStep:
    verdict === 'CONFIRMED'
      ? 'Permissions keystone is audit-clean. Continue the framework build from P2 (push the hardened classifier to mossad with the rest).'
      : 'Permissions still under-gating after 3 rounds — pause and escalate; do NOT proceed past the safety keystone.',
};
