# Phase 6 — network tool audit

Date: 2026-06-21
Host: Linux (Arch), Python 3.14.6

## Files created

- `core/tools/network.py`
- `tests/test_tools_network.py`

## Structure conformance (services.py template)

- Per-op functions (`_op_show`, `_op_status`, `_op_connections`, `_op_interfaces`,
  `_op_bring_up`, `_op_bring_down`, `_op_set_ip`) returning `ToolResult` via `run_subprocess`.
- `_DISPATCH` table keyed by op name.
- `ToolSpec` (`NETWORK_SPEC`) with per-op `OpSpec(permission_class=...)`.
- `_maybe_selinux_hint` helper (copied from services.py).
- Self-registration: `registry.register(NETWORK_SPEC)` at import time.

## Op / permission map

| Op           | Class       | Command synthesized                              |
|--------------|-------------|--------------------------------------------------|
| show         | READ        | `ip addr show`                                   |
| status       | READ        | `ip -brief addr`                                 |
| connections  | READ        | `nmcli con show`                                 |
| interfaces   | READ        | `ip link show`                                   |
| bring_up     | WRITE       | `ip link set <if> up` / `nmcli con up <conn>`    |
| bring_down   | DESTRUCTIVE | `ip link set <if> down`                          |
| set_ip       | WRITE       | `ip addr add <addr> dev <if>` / `nmcli con modify` |

## Invariants threaded

- I1: no external/network calls at runtime; every op shells out via `run_subprocess`.
- I2: no AI/LLM/agent/model/etc. in any ToolSpec description, OpSpec description,
  or ToolResult summary. Verified by the `TestI2Filter` class, which imports
  `core.agent.prompt._FORBIDDEN_AI_TERMS` (the canonical filter).
- I3: tool does NOT call `permissions.classify()` or `audit` internally;
  gate is resolved by the REPL/router.
- I4: tool does NOT write audit records; caller is responsible.
- I6: no tier/product names anywhere in the file.
- I9: missing/unknown ops return a well-formed ToolResult, never raise.

## Classifier bridge note

`bring_down` emits `ip link set <if> down`. The hardened classifier sees
`ip ... set` matched by `_SUBCMD_OVERRIDE_WRITE_PATTERNS` (WRITE at minimum),
and the `down` direction escalates the link. In a non-interactive
`ExecContext`, `classify()` returns `Gate.REFUSE`.  The P6.8 consolidation
agent will add the `synthesize_command` branch in `repl.py` — this tool
does not touch `repl.py`.

## Test run

Command: `python3 -m unittest tests.test_tools_network`
Result:  Ran 60 tests in 0.009s — OK (0 failures, 0 errors)
