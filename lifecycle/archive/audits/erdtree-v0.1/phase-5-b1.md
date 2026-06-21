# Phase 5 — SHELL-CORE slice — evidence (b1)

Date: 2026-06-21
Host: Linux (Arch), bash + systemctl + ollama present. python3 3.14.6. pytest NOT installed.
Scope touched: shell/ (dispatch, prompt, passthrough, shell.py, __init__, hooks/), tests/test_dispatch.py, tests/test_deadman.py.
NOT touched: core/, os/.

## 1. Drafts verified against the LOCKED UX (completed/fixed as needed)

- shell/dispatch.py — VERIFIED CORRECT, no change. Implements the locked 5-rule
  conservative heuristic exactly: (R3) first token /, ./, ../ -> RAW; (R4) first
  token not on PATH -> ENGLISH; (R5) on PATH + flag token -> RAW; (R6) on PATH +
  path arg ('/') -> RAW; (R7) otherwise -> ENGLISH (safe default). Plus (R1) "!!"
  -> TOGGLE signal, (R2) "!cmd" -> RAW with the '!' stripped. shlex parse failure
  falls to ENGLISH (conservative). 0 mis-dispatches confirmed (see §3).
- shell/prompt.py — VERIFIED CORRECT, no change. NL = "[NL] ❯ " in tier color via
  an opaque-label lookup table (I6); BASH = "[BASH] $ " in pink \033[38;5;213m for
  all tiers. Tier colors match spec (marika 214 / radagon 196 / radahn 124 /
  starscourge 93). Verified literal output: NL repr '\x1b[38;5;196m[NL] ❯ \x1b[0m',
  BASH repr '\x1b[38;5;213m[BASH] $ \x1b[0m'.
- shell/passthrough.py — VERIFIED CORRECT, no change. run_command() streams a bash
  subshell (shell=True, executable=/bin/bash, inherited stdio); exec_bash() prints
  the banner then os.execvp("bash", ["bash"]) — the dead-man exec path.
- shell/hooks/startup.py — VERIFIED CORRECT, no change. Non-raising localhost-only
  probe of /api/tags with a 5s hard timeout; optional model-loaded check; returns
  HealthResult(ok, message) and NEVER raises (catch-all -> ok=False) so the
  dead-man path always fires. I1: only localhost touched.

## 2. shell/shell.py — BUILT (new)

- Wraps core.agent.repl.Repl via core.agent.main.build_repl — does NOT reinvent
  the loop. Drives Repl.run_turn DIRECTLY (not core.agent.repl.interactive_loop,
  which swallows ConnectionError) so the mid-session dead-man guard can fire.
- MODE STATE: NL default; "!!" toggles PERMANENTLY to BASH and back (ShellState).
  BASH mode runs every line raw (except "!!"); "!cmd" runs one raw command and
  STAYS in NL; ENGLISH -> Repl.run_turn.
- DEAD-MAN (I9), OUTERMOST: run()'s first action is _guarded_start() = health
  check + build_repl, each wrapped so ANY failure (unreachable / not-ready /
  build raises / probe crashes) -> exec bash with a LOUD plain banner. MID-SESSION:
  a ConnectionError from run_turn -> exec bash loudly. Non-ConnectionError per-turn
  errors print one line and keep the session (one bad turn never kills it).
- Tier label comes from OUTSIDE (ERDTREE_TIER env), opaque, passed to prompt only
  (I6 — no tier-name branching). I1: shell.py opens no sockets (grep clean). I2:
  all user-facing strings (prompts + both banners) scanned clean of
  ai/llm/model/agent/agentic. I7: no "Rocky" in any user-facing string.
- All collaborators are injectable seams (repl_factory, health_check, read_line,
  exec_bash, run_command) so the shell is fully testable without Ollama and
  without replacing the test runner.

## 3. Tests — RUN ON THIS HOST (not deferred)

Command: `python3 -m unittest tests.test_dispatch tests.test_deadman -v`
Result: Ran 27 tests — OK (0 failures, 0 errors).

- test_dispatch.py (18 tests): raw-with-flags (df -h, ls -la /tmp, grep -r foo
  /etc), raw-with-path (cat /etc/fstab, grep foo /var/log/messages), path
  invocation (/usr/bin/uptime, ./build.sh, ../scripts/run), single-word-on-PATH ->
  ENGLISH (pwd, whoami), English-not-on-PATH (show me failing services, why is
  nginx not starting, ...), "!cmd" -> always RAW (even non-PATH token), "!!" ->
  TOGGLE. A labeled CORPUS asserts 0 mis-dispatches AND a cardinal-sin check that
  no ENGLISH line ever becomes RAW. On-PATH cases monkeypatch shutil.which for
  host-independence (permanent gate, not host-flaky); df/ls/grep/cat/pwd/whoami
  also genuinely on PATH here.
  Note: "systemctl status nginx" has no flag and no '/', so the conservative rule
  routes it to ENGLISH (safe false-English, the loop handles it) — NOT a
  mis-dispatch (a false-RAW would be the sin; this is not one).

- test_deadman.py (9 tests): STARTUP fallback fires on (a) health ok=False,
  (b) build_repl raising, (c) a crashing health probe; MID-SESSION fallback fires
  on a ConnectionError during a turn; a non-ConnectionError turn does NOT fall back
  (rc 0, session preserved); both banners + the live passthrough.exec_bash route
  are I2-clean (regex standalone-word check over ai/llm/model/agent/agentic) and
  loud ("BASH"). Exec is exercised safely: injected fake exec_bash raises a
  sentinel; one test patches passthrough.os.execvp to prove real routing without
  replacing the runner.

Integration smoke (ad-hoc, passed): toggle persists across lines, "!cmd" stays in
NL, English routed to run_turn, no dead-man fired when healthy.

## 4. Regression check on the existing suite

Command: `python3 -m unittest discover -s tests`
Result: 11 ERRORS — ALL are `ModuleNotFoundError: No module named 'pytest'` at
import time in pre-existing pytest-style modules (test_audit, test_permissions,
test_repl, test_router, test_snapshot, test_ollama_roundtrip, test_run_bench,
test_tools_{registry,services,packages,logs}). These are a PRE-EXISTING host
condition (pytest not installed on this build host) affecting the whole repo's
pytest-based suite — NOT a regression from this slice and NOT in files this slice
touched. The pure-unittest modules (test_dispatch, test_deadman, test_main) load
and run; the two new ones are green. No code in core/ or os/ was modified.

## 5. Legitimately deferred (environment-blocked only)

- Live systemd-unit ACTIVATION and PAM LOGIN wiring (os/systemd, os/pam) — need a
  provisioned target box + root + /etc/passwd edits (install/Phase 11). The unit/
  conf/pam FILES are out of THIS slice's scope (shell-core only); shell logic
  itself is fully tested here, NOT deferred.

## Verdict
PASS. Both new test files green on this host (27/27). 0 mis-dispatches on the
corpus. I1/I2/I6/I7/I9 upheld in shell/. core/ and os/ untouched.
