# Erdtree v0.1 — Build Audit Log (FINAL.md)

This file accumulates per-phase rollup entries as phases complete.
Phases not yet listed are outstanding. The plan at
`lifecycle/pending/plans/erdtree-v0.1-buildout.txt` REMAINS IN pending/
because phases 6–11 are not yet built; moving it to archive/ would falsely
claim the entire buildout is done.

---

## Phase 5 Rollup — Shell Core + OS Integration

**Date:** 2026-06-21
**Status:** COMPLETE — audit-duo PASS (B1 shell-core + B2 OS integration)

### Files Created

| File | Purpose |
|------|---------|
| `shell/shell.py` | Main shell entry-point: NL/BASH dispatch, dead-man fallback (I9), injectable seams for full testability |
| `os/systemd/erdtree-agent.service` | systemd unit for the erdtree agent (Wants= ollama.service, no hard Requires=, TimeoutStartSec=15) |
| `os/journald/erdtree.conf` | journald drop-in: persistent storage, 500 MB cap, 90-day retention, compression |
| `os/pam/erdtree` | PAM stack snippet: delegates auth to system-auth, honors nologin, all Erdtree-specific session items optional |
| `tests/test_dispatch.py` | 18-test suite: 0 mis-dispatches across the full dispatch-rule corpus; cardinal-sin check (no ENGLISH line becomes RAW) |
| `tests/test_deadman.py` | 9-test suite: startup + mid-session dead-man fallback paths; I2-clean banner check |

### Completed / Verified Drafts (pre-existing, verified correct)

- `shell/dispatch.py` — locked 5-rule conservative heuristic (R3–R7 + R1/R2), 0 mis-dispatches
- `shell/prompt.py` — NL/BASH prompts, tier colors via opaque lookup (I6)
- `shell/passthrough.py` — `run_command()` streaming + `exec_bash()` dead-man exec path
- `shell/hooks/startup.py` — non-raising localhost-only Ollama health probe (I1)

### Test Command and Tally

```
python3 -m unittest tests.test_dispatch tests.test_deadman -v
```

Result: **27 tests — OK (0 failures, 0 errors)**

- `test_dispatch.py`: 18 tests green
- `test_deadman.py`: 9 tests green

Pre-existing pytest-based modules (test_audit, test_permissions, test_repl, test_router,
test_snapshot, test_ollama_roundtrip, test_run_bench, test_tools_*) produce
`ModuleNotFoundError: No module named 'pytest'` on the build host (pytest not installed).
This is a pre-existing host condition; none of those modules were touched by Phase 5 and
all were erroring before this phase.

### Audit-Duo Verdict

**PASS** — two independent adversarial reviews:

- **B1 (shell-core):** shell/shell.py built and tested. 27/27 tests green. 0 mis-dispatches.
  I1/I2/I6/I7/I9 upheld throughout shell/. core/ and os/ untouched by this sub-slice.
  See `phase-5-b1.md`.

- **B2 (OS integration):** erdtree-agent.service, erdtree.conf, os/pam/erdtree authored,
  I2/I7-clean, structurally validated (systemd-analyze verify passes with substituted
  build-host paths). See `phase-5-b2.md`.

### Honestly Deferred Items

The following are environment-blocked only — not design gaps or skipped work:

| Item | Reason / Resolution Phase |
|------|--------------------------|
| Live systemd unit activation | Requires provisioned target host + root + `/opt/erdtree/` install + `erdtree` user/group. Phase 11 (install scripts). |
| PAM login wiring (`/etc/pam.d/` drop + `/etc/passwd` shell entry) | Requires root on a provisioned target host with `/etc/passwd` editing. Phase 11. |
| journald drop-in activation (`systemctl restart systemd-journald`) | Requires root on a provisioned target host. Phase 11. |

Shell logic itself (shell.py, dispatch, prompt, passthrough, hooks) is **fully tested** on this
host and NOT deferred.

### Plan Status

The buildout plan at `lifecycle/pending/plans/erdtree-v0.1-buildout.txt` **REMAINS IN pending/**
because this plan covers all 12 phases (P0–P11) and phases 6–11 are not yet built.
Phase 5 specifically is complete and recorded here. The plan moves to archive/ only when
all phases are done.
