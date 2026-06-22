# Phase 6 TOOL slice — core/tools/disk.py

Date: 2026-06-21
Host: Linux (Arch). pytest NOT installed → tests are stdlib `unittest`.

## What shipped
- `core/tools/disk.py` — block-device/filesystem tool, modeled EXACTLY on
  `core/tools/services.py` (per-op functions returning ToolResult via
  `run_subprocess`; `_DISPATCH` table keyed by op name; a `ToolSpec` with
  per-op `OpSpec(permission_class=...)`; self-registration via
  `registry.register(TOOL_SPEC)` at import; `_maybe_selinux_hint` copied from
  services.py). TOUCHED ONLY this file + the test.
- `tests/test_tools_disk.py` — stdlib `unittest`, 28 tests.

## Op + permission map (as built)
| op        | class       | command vector built |
|-----------|-------------|----------------------|
| usage     | READ        | `df -h [path]` |
| list      | READ        | `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT [device]` |
| smart     | READ        | `smartctl -H -A <device>` |
| mount     | WRITE       | `mount <device> <mount_point>` |
| unmount   | WRITE       | `umount <target>` |
| format    | DESTRUCTIVE | `mkfs.<fstype> <device>` |
| partition | DESTRUCTIVE | `parted <device> <directives...>` |
| wipe      | DESTRUCTIVE | `wipefs -a <device>` |
| dd_write  | DESTRUCTIVE | `dd if=<source> of=<device> bs=<bs>` |

The destructive ops build the REAL dangerous program/argv shape so the
EXISTING hardened classifier (`core/agent/permissions.py`) escalates each to
DESTRUCTIVE → CONFIRM_TYPED. The tool NEVER calls permissions or audit (A3),
NEVER self-classifies, NEVER uses psutil/pyroute2/shutil/os mutation — it only
shells out via `run_subprocess` (I1 / classifier-visibility).

## Invariants threaded
- I1: no network; no device Python libs imported; no URL-like tokens in any
  command vector (asserted).
- I2: every ToolSpec/OpSpec/ArgSpec description + every ToolResult.summary
  (success, failure, SELinux-hint, unknown-op) cleared against the canonical
  `core/agent/prompt.py::_FORBIDDEN_AI_TERMS` (imported, not re-listed).
  Caught one real violation during dev: an arg example used "gpt" (a forbidden
  term) → changed to "msdos".
- I3/I4: gate + audit are the REPL's job; this module does neither.
- I6: no tier/product names in source (asserted).
- I9: unknown op and every failure path degrade to a well-formed ToolResult;
  `_execute` never raises.

## Permission-gate verification (SC-P6.2, the keystone)
Feeding each op's synthesized command line through the real `classify()`:
- READ (usage/list/smart) → Gate.ALLOW, auto_ok=True (no gate).
- WRITE (mount/unmount) → Gate.CONFIRM.
- DESTRUCTIVE (format/partition/wipe/dd_write) → OpClass.DESTRUCTIVE,
  Gate.CONFIRM_TYPED interactively; Gate.REFUSE under
  `ExecContext(interactive=False)`.

## Test run
Command: `python3 -m unittest tests.test_tools_disk`
Result: Ran 28 tests — OK (28 passed, 0 failed, 0 errors).

Note: a combined run that also pulls in `tests/test_tools_registry.py` and
`tests/test_permissions.py` shows 2 errors — those are PRE-EXISTING files that
`import pytest` (absent on this host) and are unrelated to this slice.
`tests/test_tools_disk.py` imports zero pytest.

## Not done here (correctly out of scope for this slice)
- `synthesize_command()` branch in `core/agent/repl.py` and the import in
  `main.py` — those are the P6.8 consolidation (single-writer on repl.py /
  main.py). This tool self-registers correctly so that step can wire it.
