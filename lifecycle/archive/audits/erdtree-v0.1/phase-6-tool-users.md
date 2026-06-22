# Phase 6 — TOOL slice: core/tools/users.py

Status: PASS

## What shipped
- `core/tools/users.py` — local user-account tool, modeled EXACTLY on
  `core/tools/services.py` (per-op functions returning `ToolResult` via
  `run_subprocess`; `_DISPATCH` table keyed by op name; a `ToolSpec` with per-op
  `OpSpec(permission_class=...)`; self-registration via
  `registry.register(USERS_SPEC)` at import; the copied `_maybe_selinux_hint`).
- `tests/test_tools_users.py` — stdlib `unittest` (pytest is NOT installed on
  this Arch host).

## Ops + permission map (as specced)
| op | class | argv synthesized / shelled |
|----|-------|----------------------------|
| list | READ | `cat /etc/passwd` |
| info | READ | `id <user>` |
| add | WRITE | `useradd <user>` |
| set_shell | WRITE | `usermod -s <shell> <user>` |
| add_to_group | WRITE | `usermod -aG <group> <user>` |
| lock | DESTRUCTIVE | `usermod -L <user>` |
| delete | DESTRUCTIVE | `userdel <user>` |
| remove_from_privgroup | DESTRUCTIVE | `gpasswd -d <user> wheel` |

Note on READ ops: the spec said binaries useradd/usermod/passwd/userdel/gpasswd,
but those are all mutators. For the two READ ops the tool shells out
classifier-recognized read verbs (`cat /etc/passwd`, `id <user>`) so the faithful
command line the hardened classifier sees yields Gate.ALLOW. `getent passwd`
was rejected because `getent` is not in permissions.py `_READ_COMMANDS` and
floors to WRITE — using it would have OVER-gated every account listing.

## Invariants threaded
- I1 — only `run_subprocess`; no socket, no network. Grep gate confirms no
  psutil / pyroute2 / shutil.rmtree / os.* mutation / direct subprocess.
- I2 — every ToolSpec/OpSpec/ArgSpec description and every ToolResult.summary
  clears the CANONICAL `_AI_PATTERN` / `_FORBIDDEN_AI_TERMS` imported from
  `core/agent/prompt.py` (asserted in TestNoAILanguage). Plain Linux-operator
  language ("Listed N local accounts.", "Account 'x' locked.").
- I3 — no permissions/audit calls inside the tool; the loop resolves the gate
  from the synthesized command string. The three DESTRUCTIVE ops classify
  DESTRUCTIVE -> CONFIRM_TYPED interactively and REFUSE non-interactively
  (asserted against the live classifier).
- I4 — tool writes no audit; the loop does.
- I6 — no tier/product/model names.
- I9 — unknown op degrades to a valid ToolResult (exit_code=1), never raises.

## Tests
Command: `python3 -m unittest tests.test_tools_users`
Result: Ran 34 tests — OK (0 failures, 0 errors).

Key assertions: registry.get("users") present after import; READ ops -> ALLOW
(no gate); WRITE ops -> CONFIRM; DESTRUCTIVE ops -> CONFIRM_TYPED (interactive)
and REFUSE (non-interactive); exact argv per op; SELinux hint surfaces on AVC
stderr; I2 filter clean on all descriptions + all summaries (success, failure,
selinux-hint variants); registry dispatch path + arg validation.

## Files touched
- core/tools/users.py
- tests/test_tools_users.py

(Did NOT touch repl.py or main.py — the P6.8 consolidation adds the
synthesize_command branch + import; the tool self-registers correctly.)
