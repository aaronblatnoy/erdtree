"""finetune/simulate/fapolicyd.py — Rocky Linux 9 output simulator for the 'fapolicyd' tool.

Public API
----------
simulate_fapolicyd(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/fapolicyd.py
    args : dict of op arguments (may be {} for ops with no required args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real fapolicyd / systemctl behaviour on Rocky Linux 9:
    0 — success
    1 — operation failed (rule error, daemon not responding)
    3 — service loaded but inactive (systemctl status)
* stdout/stderr reflect actual fapolicyd-cli and systemctl output formats.
* Failure triggers are deterministic: paths containing known failure tokens
  ("notfound", "noexist", "invalid", "bogus", "missing") return failure cases,
  plus a hash-based ~6% scatter for variety.
* ctx controls whether fapolicyd is active: checked via active_services list
  or string presence.

I2 compliance
-------------
All summary strings are I2-clean. No AI/LLM/model/agent/neural language appears.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (avoids circular deps when the
Phase-13 __init__.py imports simulate modules before coreimports is settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _fapolicyd_is_active(ctx: Any) -> bool:
    """Return True if fapolicyd appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("fapolicyd" in s for s in active)
    if isinstance(ctx, str):
        return "fapolicyd" in ctx
    # Default: assume running so most traces show a healthy state
    return True


def _path_failure(path: str) -> bool:
    """Deterministically decide if a path should trigger a failure response.

    Triggers: path contains a known error token; OR a hash-based ~6% scatter.
    """
    lower = path.lower()
    for tok in ("notfound", "noexist", "invalid", "bogus", "missing"):
        if tok in lower:
            return True
    h = int(hashlib.md5(path.encode()).hexdigest(), 16)
    return h % 16 == 0


def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)
    active = _fapolicyd_is_active(ctx)

    if active:
        stdout = (
            "● fapolicyd.service - File Access Policy Daemon\n"
            "     Loaded: loaded (/usr/lib/systemd/system/fapolicyd.service;"
            " enabled; preset: disabled)\n"
            "     Active: active (running) since Thu 2026-07-03 00:01:00 UTC;"
            " 8h 14min ago\n"
            "   Main PID: 1842 (fapolicyd)\n"
            "      Tasks: 3 (limit: 23168)\n"
            "     Memory: 18.6M\n"
            "        CPU: 0.421s\n"
            "     CGroup: /system.slice/fapolicyd.service\n"
            "             └─1842 /usr/sbin/fapolicyd\n"
            "\n"
            f"Jul 03 00:01:00 {host} systemd[1]: Started File Access Policy Daemon.\n"
            f"Jul 03 00:01:00 {host} fapolicyd[1842]: Starting to listen for events.\n"
        )
        return _make_result(0, stdout, "", "fapolicyd service is active and running.")
    else:
        stdout = (
            "○ fapolicyd.service - File Access Policy Daemon\n"
            "     Loaded: loaded (/usr/lib/systemd/system/fapolicyd.service;"
            " disabled; preset: disabled)\n"
            "     Active: inactive (dead)\n"
        )
        return _make_result(3, stdout, "", "fapolicyd service reported status exit 3.")


def _sim_list_rules(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    active = _fapolicyd_is_active(ctx)
    if not active:
        stderr = "fapolicyd-cli: error: cannot connect to fapolicyd daemon\n"
        return _make_result(1, "", stderr, "Failed to list fapolicyd rules (exit 1).")

    stdout = (
        "Fapolicyd rule list:\n"
        "allow perm=open exe=/usr/bin/rpm : all\n"
        "allow perm=open exe=/usr/bin/python3 : all\n"
        "allow perm=open exe=/usr/bin/python3.9 : all\n"
        "allow perm=any trust=1 : all\n"
        "allow perm=any exe=/usr/lib/systemd/systemd : all\n"
        "allow perm=open all : ftype=text/plain\n"
        "allow perm=open all : ftype=application/x-python\n"
        "allow perm=open all : ftype=application/x-rpm\n"
        "deny perm=any all : ftype=application/x-executable dir=/tmp\n"
        "deny perm=any all : ftype=application/x-sharedlib dir=/tmp\n"
        "deny perm=execute all : ftype=application/x-executable dir=/var/tmp\n"
        "deny perm=any all : all\n"
    )
    line_count = stdout.count("\n")
    return _make_result(0, stdout, "", f"Listed {line_count} fapolicyd rule entries.")


def _sim_allow(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    path = args.get("path", "/unknown/path")

    if _path_failure(path):
        stderr = (
            f"fapolicyd-cli: error: failed to add rule for '{path}'\n"
            "fapolicyd-cli: check that the path exists and fapolicyd is running\n"
        )
        return _make_result(
            1, "", stderr,
            f"Failed to add allow rule for '{path}' (exit 1).",
        )

    stdout = f"Rule added: allow perm=any all : path={path}\n"
    return _make_result(0, stdout, "", f"Allow rule added for path '{path}'.")


def _sim_deny(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    path = args.get("path", "/unknown/path")

    if _path_failure(path):
        stderr = (
            f"fapolicyd-cli: error: failed to add rule for '{path}'\n"
            "fapolicyd-cli: check that the path exists and fapolicyd is running\n"
        )
        return _make_result(
            1, "", stderr,
            f"Failed to add deny rule for '{path}' (exit 1).",
        )

    stdout = f"Rule added: deny perm=any all : path={path}\n"
    summary = (
        f"Deny rule added for path '{path}'. "
        "Denying a critical system path can prevent logins or system execution — "
        "run 'update' to apply and verify access is not broken."
    )
    return _make_result(0, stdout, "", summary)


def _sim_update(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    active = _fapolicyd_is_active(ctx)
    if not active:
        stderr = "fapolicyd-cli: error: cannot connect to fapolicyd daemon\n"
        return _make_result(1, "", stderr, "fapolicyd rule reload failed (exit 1).")

    stdout = "Rules have been updated\n"
    return _make_result(0, stdout, "", "fapolicyd rules reloaded successfully.")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status": _sim_status,
    "list_rules": _sim_list_rules,
    "allow": _sim_allow,
    "deny": _sim_deny,
    "update": _sim_update,
}


def simulate_fapolicyd(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'fapolicyd' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name — one of: status, list_rules, allow, deny, update.
    args : argument dict (may be {} for ops with no required args).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_services' list and 'hostname' key.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_fapolicyd: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
