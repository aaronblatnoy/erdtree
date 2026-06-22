# Phase 6 TOOL slice — core/tools/firewall.py

Binary: `firewall-cmd` (ABSENT on this Linux/Arch build host -> run_subprocess mocked in all tests).

## Deliverables
- `core/tools/firewall.py` — faithful tool modeled EXACTLY on `core/tools/services.py`
  (per-op functions returning ToolResult via `run_subprocess`; `_DISPATCH` table
  keyed by op name; a `ToolSpec` with per-op `OpSpec(permission_class=...)`;
  self-registration `registry.register(FIREWALL_SPEC)` at import time;
  `_maybe_selinux_hint` copied from services.py).
- `tests/test_tools_firewall.py` — stdlib `unittest` (pytest is NOT installed here).

## Op + permission map (OpSpec class is ADVISORY; the hardened classifier resolves the real gate)
| op | class |
|----|-------|
| list, get_zones, query | READ |
| add_service, add_port, remove_service, remove_port, reload, set_default_zone | WRITE |
| panic_on | DESTRUCTIVE |

- `set_default_zone` = WRITE per spec; remote-SSH lockout stakes are raised by the
  EXISTING classifier via `ExecContext.remote` on the synthesized command line
  (P6.8 owns synthesize_command — not edited here).
- `panic_on` -> synthesized `firewall-cmd --panic-on`, which the existing
  classifier (`_classify_argv` firewall-cmd `--panic-on` rule) escalates to
  DESTRUCTIVE -> CONFIRM_TYPED, and REFUSE under a non-interactive ExecContext.
  Verified in tests TestClassifierIntegration.

## Invariants honored
- I1: no network/socket; shells out only via `run_subprocess`.
- I2: every OpSpec/ToolSpec description, every ArgSpec description, and every
  ToolResult.summary asserted clean against the CANONICAL filter — the test
  imports `_AI_PATTERN` (built from `_FORBIDDEN_AI_TERMS`) from
  `core/agent/prompt.py` rather than re-listing terms. "zone/service/port"
  contain no forbidden whole-words.
- I3/I4: the tool NEVER calls permissions or audit (A3) — the REPL resolves the
  gate and writes the audit.
- I6: zero tier/product/model names.
- I9: unknown op -> a well-formed ToolResult (never an exception).
- SELinux hint surfaced on AVC-shaped stderr (AVC denials likely on firewalld).

## STRICT rules
- subprocess ONLY via `run_subprocess` (no psutil/pyroute2/os.* mutation) so the
  classifier can reason about the synthesized command vector.
- `_maybe_selinux_hint` helper copied verbatim from services.py.

## Tests
Command: `python3 -m unittest tests.test_tools_firewall`
Result: Ran 40 tests — OK (0 failures, 0 errors).

Coverage: registry.get("firewall") present after import; READ/WRITE/DESTRUCTIVE
OpSpec classes; classifier ALLOW for READ ops, DESTRUCTIVE/CONFIRM_TYPED +
non-interactive REFUSE for panic_on; per-op success/failure ToolResults;
faithful command vectors (every cmd[0]=="firewall-cmd"; panic_on emits
`--panic-on`); SELinux hint surfacing; ToolResult structure; registry.dispatch
arg-validation; full I2 sweep over descriptions + summaries.

Note: `tests/test_permissions.py` (pre-existing) imports `pytest` and errors on
collection on this host — unrelated to this slice and out of scope (TOUCH ONLY
firewall.py + test_tools_firewall.py).

## TOUCHED
- core/tools/firewall.py (new)
- tests/test_tools_firewall.py (new)
NOT touched: repl.py, main.py (P6.8 owns synthesize_command + the import).
