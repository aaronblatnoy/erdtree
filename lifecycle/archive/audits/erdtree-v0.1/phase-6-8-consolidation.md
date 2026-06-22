# Phase 6 Consolidation (P6.8) — Classifier Bridge — Evidence

Date: 2026-06-21
Scope (single-writer pass): `core/agent/repl.py` (synthesize_command only),
`core/agent/main.py` (imports only), `tests/test_synthesize_command.py` (new).
NOT touched: permissions.py, audit.py, router.py, the dispatch/gate/audit path,
the `history=[]` seam (those are P8.c).

## What was done

1. `synthesize_command()` in `core/agent/repl.py` extended with one branch per
   new tool (docs, hardware, disk, users, firewall, network, processes, files).
   Each renders the FAITHFUL command line the FROZEN classifier
   (`core/agent/permissions.classify`) already reasons over. Destructive ops
   emit the REAL dangerous argv so the classifier ESCALATES:
     - disk.format   -> `mkfs.<fstype> <device>`
     - disk.partition-> `parted <device> <cmd...>`
     - disk.wipe     -> `wipefs -a <device>`
     - disk.dd_write -> `dd if=<src> of=<device> bs=<bs>`
     - users.lock    -> `usermod -L <user>`
     - users.delete  -> `userdel <user>`
     - users.remove_from_privgroup -> `gpasswd -d <user> wheel`
     - firewall.panic_on -> `firewall-cmd --panic-on`
     - processes.signal(-1) -> `kill -1 <pid>`
     - files.remove(-r/-f) -> `rm -rf <path>`
   docs.retrieve renders a fixed READ sentinel (`man -k`) so a pure read is
   ALLOW with no gate friction (I8).
   CONSERVATISM RULE honored: any unrenderable op (and every write whose precise
   render is unnecessary to reach its class) falls through to `f"{tool} {op}"`
   (the classifier's WRITE floor). No branch UNDER-states blast radius.

2. `core/agent/main.py`: added the 7 P6 tool imports (network, firewall, users,
   disk, processes, hardware, files) — import side-effect self-registers each —
   plus a GUARDED docs import (try/except) so a missing/unreadable corpus index
   degrades to "docs absent" rather than crashing build_repl (I9). No P8
   memory/facts/episodic wiring added (left for P8.c).

3. `tests/test_synthesize_command.py` (stdlib unittest): exhaustive gate over
   EVERY (tool, op) for all 7 P6 tools + docs (62-row table + a coverage test
   that asserts no registered op is left unverified). The lockout/data-loss set
   classifies DESTRUCTIVE -> CONFIRM_TYPED interactive AND REFUSE
   non-interactive. docs -> READ -> ALLOW. Registry test asserts
   list_tools() == the full 10 operator tools + docs (11), schemas build clean,
   zero I2-forbidden terms in any advertised string or ToolSpec/OpSpec
   description (imports prompt.py `_FORBIDDEN_AI_TERMS`). AST grep gate: no P6
   tool imports psutil/pyroute2 or calls shutil.rmtree / os.remove / os.unlink /
   os.rmdir directly.

## DOCUMENTED DEVIATION — network.bring_down (WRITE floor, not DESTRUCTIVE)

The plan's literal example (and its keystone list) wants `network.bring_down`
to classify DESTRUCTIVE. The FROZEN classifier (permissions.py) has NO
destructive rule for a network-interface teardown: every faithful rendering
(`ip link set <if> down`, `ifconfig <if> down`, `ifdown`, `nmcli con down`,
`ip link delete`, `ip route flush`, `nmcli networking off`, `systemctl stop
NetworkManager`) classifies WRITE -> CONFIRM. P6.8 must NOT modify/weaken
permissions.py (I3) and may not exceed its file scope, so bring_down is rendered
faithfully as `ip link set <if> down` and lands at the WRITE floor: it is STILL
GATED (CONFIRM interactive, REFUSE non-interactive) and NEVER auto-run — the
CONSERVATISM rule forbids only UNDER-running, which this does not do. The
existing `tests/test_tools_network.py` already resolved the same tension the
same way (its synthesized-command assertion only requires "NOT ALLOW"). Raising
bring_down to DESTRUCTIVE would require a one-line addition to permissions.py's
argv logic (an `ip link set <if> down` / `ifdown` rule) — out of scope here;
recommend it for the permissions owner.

## Test commands + tallies

- Gate test (required command):
  `python3 -m unittest tests.test_synthesize_command`
  -> Ran 13 tests, OK (0 failures). 62-row (tool,op) subtest table + lockout
     set + docs + registry/schema/I2 + AST grep gate all green.

- Full suite (required command), bare system python3:
  `python3 -m unittest discover -s tests`
  -> 11 loader errors + 3 fails. ALL environment-only: the bare /usr/bin/python3
     lacks `pytest` (11 pytest-style modules fail to import) and the sqlite-vec
     rag backend (rag/docs tests). NOT regressions.

- Full suite under the repo venv (.venv has pytest + sqlite-vec — the real test
  environment):
  `.venv/bin/python -m unittest discover -s tests`  -> Ran 425 tests, OK (3 skipped).
  `.venv/bin/python -m pytest -q`                   -> 1730 passed, 14 skipped,
                                                        371 subtests passed, 0 failed.
  Pre-P6 core (no regression):
  `.venv/bin/python -m pytest tests/test_permissions.py tests/test_repl.py
     tests/test_router.py tests/test_audit.py tests/test_tools_registry.py -q`
  -> 947 passed.
  rag/docs: `.venv/bin/python -m pytest tests/test_rag_retrieve.py
     tests/test_rag_index.py tests/test_tools_docs.py -q` -> 51 passed.

## Invariants threaded
I1 no egress (synthesize is pure string-building; classifier is pure logic).
I2 no AI/LLM/model/agent terms — enforced by importing prompt._FORBIDDEN_AI_TERMS
   in the schema/description scan. I3 gate stays in the classifier; P6 only
   synthesizes (permissions.py untouched). I4 audit unchanged (REPL owns it).
   I6 tool knobs read opaquely; no tier names added. I9 docs import guarded so a
   missing index degrades, never crashes build_repl.
