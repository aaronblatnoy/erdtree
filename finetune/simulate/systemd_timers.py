"""finetune/simulate/systemd_timers.py — Rocky Linux 9 output simulator for the 'systemd_timers' tool.

Public API
----------
simulate_systemd_timers(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/systemd_timers.py
    args : dict of op arguments (may be sparse; defaults are applied per-op)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict with 'hostname' and 'active_services' lists.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Output matches real Rocky Linux 9 systemctl / systemd-run output shapes.
* Failure triggers are deterministic: timer names containing "notfound",
  "missing", "bogus", "broken", or "fail" return failure cases. Names without
  a dot also trigger not-found. A hash-based ~15% scatter adds variety.
* ctx is used for hostname extraction in log-style output.

I2 compliance
-------------
All summary strings are I2-clean. No AI/LLM/model/agent/agentic/neural/
inference/ollama language anywhere in this module.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (avoids circular deps).
The 4-key dict mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _timer_is_active(timer: str, ctx: Any) -> bool:
    """Return True if the timer appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return timer in active or any(timer in s for s in active)
    if isinstance(ctx, str):
        return timer in ctx
    return False


def _timer_not_found(timer: str) -> bool:
    """Deterministically decide if a timer name should trigger a not-found error."""
    lower = timer.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus"):
        if tok in lower:
            return True
    # Names with no dot are unusual for systemd unit names
    if "." not in timer:
        return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(timer.encode()).hexdigest(), 16)
    return h % 20 == 0


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

def _sim_list_timers(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: systemctl list-timers --all --no-pager"""
    host = _hostname(ctx)

    # Realistic Rocky 9 list-timers output
    stdout = (
        "NEXT                        LEFT          LAST                        PASSED       UNIT                         ACTIVATES                     \n"
        "Sat 2026-07-04 00:00:00 UTC 13h left      Fri 2026-07-03 00:00:01 UTC 10h ago      logrotate.timer              logrotate.service             \n"
        "Sat 2026-07-04 01:00:00 UTC 14h left      Fri 2026-07-03 01:00:08 UTC 9h ago       dnf-makecache.timer          dnf-makecache.service         \n"
        "Sat 2026-07-04 02:30:00 UTC 15h left      Fri 2026-07-03 02:30:03 UTC 8h ago       backup.timer                 backup.service                \n"
        "Mon 2026-07-06 00:00:00 UTC 2 days left   Mon 2026-06-29 00:00:01 UTC 4 days ago   fstrim.timer                 fstrim.service                \n"
        "\n"
        "4 timers listed.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Timer list retrieved (10 output lines).",
    )


def _sim_timer_show(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: systemctl show <timer> --no-pager"""
    timer = args.get("timer", "unknown.timer")

    if _timer_not_found(timer):
        stderr = f"Unit {timer} could not be found.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Timer unit '{timer}' was not found in the systemd unit database.",
        )

    active = _timer_is_active(timer, ctx)
    state = "active" if active else "inactive"
    timer_base = timer.split(".")[0]

    stdout = (
        f"Id={timer}\n"
        f"Names={timer}\n"
        f"Description={timer_base.capitalize()} Timer\n"
        f"LoadState=loaded\n"
        f"ActiveState={state}\n"
        f"SubState=waiting\n"
        f"UnitFileState=enabled\n"
        f"NextElapseUSecRealtime=1751587200000000\n"
        f"LastTriggerUSec=1751500800000000\n"
        f"Result=success\n"
        f"TimersCalendar=OnCalendar=daily\n"
        f"Unit={timer_base}.service\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Properties for timer unit '{timer}' retrieved.",
    )


def _sim_create(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tee /etc/systemd/system/<timer> then systemctl daemon-reload"""
    timer = args.get("timer", "unknown.timer")
    content = args.get("content", "")

    # Simulate permission errors for root-only paths deterministically
    h = int(hashlib.md5((timer + "create").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = f"tee: /etc/systemd/system/{timer}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to write timer unit '{timer}': permission denied on the unit file path.",
        )

    unit_path = f"/etc/systemd/system/{timer}"
    stdout = content  # tee echoes stdin to stdout
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Timer unit '{timer}' created at '{unit_path}' and systemd reloaded.",
    )


def _sim_enable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: systemctl enable <timer>"""
    timer = args.get("timer", "unknown.timer")

    if _timer_not_found(timer):
        stderr = f"Failed to enable {timer}: Unit {timer} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Timer unit '{timer}' could not be enabled because it was not found.",
        )

    timer_base = timer.split(".")[0]
    stdout = (
        f"Created symlink /etc/systemd/system/timers.target.wants/{timer}"
        f" → /usr/lib/systemd/system/{timer}.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Timer unit '{timer}' enabled at boot.",
    )


def _sim_disable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: systemctl disable <timer>"""
    timer = args.get("timer", "unknown.timer")

    if _timer_not_found(timer):
        stderr = f"Failed to disable {timer}: Unit {timer} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Timer unit '{timer}' could not be disabled because it was not found.",
        )

    stdout = f"Removed /etc/systemd/system/timers.target.wants/{timer}.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Timer unit '{timer}' disabled; it will not start automatically at boot.",
    )


def _sim_systemd_run(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: systemd-run [--unit=<name>] [--on-calendar=<spec>] <command...>"""
    command = args.get("command", "")
    unit_name = args.get("unit_name") or ""
    on_calendar = args.get("on_calendar") or ""

    if not command.strip():
        stderr = "systemd-run: no command specified\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="systemd-run failed: no command was specified.",
        )

    # Simulate occasional failures for commands that look broken
    h = int(hashlib.md5(command.encode()).hexdigest(), 16)
    if h % 18 == 0:
        stderr = (
            "Failed to start transient service unit: "
            "Unit name already in use.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="systemd-run failed to schedule command: transient unit name already in use.",
        )

    label = unit_name if unit_name else "run-" + hashlib.md5(command.encode()).hexdigest()[:8]
    if on_calendar:
        stdout = (
            f"Running as unit: {label}.service\n"
            f"Will run on calendar: {on_calendar}\n"
        )
        summary = f"One-shot command scheduled via systemd-run as '{label}' unit."
    else:
        stdout = f"Running as unit: {label}.service\n"
        summary = f"One-shot command scheduled via systemd-run as '{label}' unit."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list-timers": _sim_list_timers,
    "timer-show":  _sim_timer_show,
    "create":      _sim_create,
    "enable":      _sim_enable,
    "disable":     _sim_disable,
    "systemd-run": _sim_systemd_run,
}


def simulate_systemd_timers(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'systemd_timers' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           systemd_timers ToolSpec (list-timers, timer-show, create, enable,
           disable, systemd-run).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'hostname' and 'active_services' lists.

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
            f"simulate_systemd_timers: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
