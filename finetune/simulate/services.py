"""finetune/simulate/services.py — Rocky Linux 9 output simulator for the 'services' tool.

Public API
----------
simulate_services(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 8 real operations declared in core/tools/services.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Checked via isinstance; both forms are supported so the simulator
           works whether generate.py passes the raw snapshot_text string or a
           richer profile dict.

Realism model
-------------
* Exit codes mirror real systemctl / journalctl behaviour:
    0  — success
    1  — operation failed (e.g. dependency error, already-stopped)
    3  — unit is loaded but inactive/failed  (systemctl status)
    4  — unit not found in systemd  (systemctl status / control ops)
    5  — unit not found for control ops (start/stop/etc. on unknown name)
* stdout/stderr reflect the actual Rocky 9 systemctl output format (cgroups v2
  style, with the ● active/inactive/failed bullets, PID, CGroup lines).
* Failure triggers are deterministic: a unit whose normalised name is NOT
  recognised as a plausible service name (no '.' separator at all, or the
  literal token "notfound"/"noexist"/"broken"/"fail" appears in the name)
  returns a failure case so traces teach error handling.  A ~20% random
  scatter (hash-based, fully deterministic) adds variety among otherwise
  valid-looking unit names.
* ctx is used to decide whether a unit is currently active: if the unit name
  appears in ctx (as a string) or in ctx["active_services"] (as a dict),
  the status op reports it running.

I2 compliance
-------------
All `summary` strings are I2-clean.  The assert_no_ai_language guard is NOT
called inline (to keep this module fast and dependency-light for tests), but
the test_i2.py suite asserts every returned summary.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_is_active(unit: str, ctx: Any) -> bool:
    """Return True if the unit appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return unit in active or any(unit in s for s in active)
    if isinstance(ctx, str):
        return unit in ctx
    return False


def _unit_has_failed(unit: str, ctx: Any) -> bool:
    """Return True if the unit appears in the failed-services list."""
    if isinstance(ctx, dict):
        failed: list[str] = ctx.get("failed_services", [])
        return unit in failed or any(unit in s for s in failed)
    return False


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic log lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        # Try to parse "Hostname: <value>" from the snapshot text
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _unit_not_found(unit: str) -> bool:
    """Deterministically decide if a unit name should trigger a not-found error.

    Triggers: the token "notfound", "noexist", "broken", or "fail" appears in
    the lowercase unit name; OR the name has no dot (not a properly-formed
    unit file name); OR a hash-based 15% scatter adds variety.
    """
    lower = unit.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus"):
        if tok in lower:
            return True
    # A bare name with no dot is unusual for systemd; treat as not found
    if "." not in unit:
        return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(unit.encode()).hexdigest(), 16)
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

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")
    host = _hostname(ctx)

    if _unit_not_found(unit):
        stderr = (
            f"Unit {unit} could not be found.\n"
        )
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' was not found in the systemd unit database.",
        )

    if _unit_has_failed(unit, ctx):
        stdout = (
            f"● {unit} - {unit.split('.')[0].capitalize()} Service\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/{unit}; enabled; preset: disabled)\n"
            f"     Active: failed (Result: exit-code) since Thu 2026-07-03 04:12:33 UTC; 4h 22min ago\n"
            f"    Process: 12847 ExecStart=/usr/sbin/{unit.split('.')[0]} (code=exited, status=1/FAILURE)\n"
            f"   Main PID: 12847 (code=exited, status=1/FAILURE)\n"
            f"        CPU: 18ms\n"
            f"\n"
            f"Jul 03 04:12:33 {host} systemd[1]: {unit}: Main process exited, code=exited, status=1/FAILURE\n"
            f"Jul 03 04:12:33 {host} systemd[1]: {unit}: Failed with result 'exit-code'.\n"
            f"Jul 03 04:12:33 {host} systemd[1]: Failed to start {unit.split('.')[0].capitalize()} Service.\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary=f"Unit '{unit}' is loaded but in a failed state.",
        )

    active = _unit_is_active(unit, ctx)
    if active:
        pid = 1000 + (sum(ord(c) for c in unit) % 8000)
        stdout = (
            f"● {unit} - {unit.split('.')[0].capitalize()} Service\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/{unit}; enabled; preset: disabled)\n"
            f"     Active: active (running) since Thu 2026-07-03 00:01:04 UTC; 8h 34min ago\n"
            f"   Main PID: {pid} ({unit.split('.')[0]})\n"
            f"      Tasks: 4 (limit: 23168)\n"
            f"     Memory: 48.2M\n"
            f"        CPU: 1.234s\n"
            f"     CGroup: /system.slice/{unit}\n"
            f"             └─{pid} /usr/sbin/{unit.split('.')[0]} -DFOREGROUND\n"
            f"\n"
            f"Jul 03 00:01:04 {host} systemd[1]: Started {unit.split('.')[0].capitalize()} Service.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Unit '{unit}' is active and running.",
        )
    else:
        stdout = (
            f"○ {unit} - {unit.split('.')[0].capitalize()} Service\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/{unit}; disabled; preset: disabled)\n"
            f"     Active: inactive (dead)\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary=f"Unit '{unit}' is loaded but currently inactive.",
        )


def _sim_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")

    if _unit_not_found(unit):
        stderr = f"Failed to start {unit}: Unit {unit} not found.\n"
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be started because it was not found.",
        )

    # Check if already active — still succeeds for systemctl start (idempotent on most units)
    active = _unit_is_active(unit, ctx)
    if active:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"Unit '{unit}' was already running; start command completed without error.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Unit '{unit}' started successfully.",
    )


def _sim_start_failure(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Explicit dependency-failure variant — returned when unit hash hits failure branch."""
    unit = args.get("unit", "unknown.service")
    host = _hostname(ctx)
    stderr = (
        f"Job for {unit} failed because the control process exited with error code.\n"
        f"See 'systemctl status {unit}' and 'journalctl -xeu {unit}' for details.\n"
    )
    stdout = (
        f"Jul 03 10:15:22 {host} systemd[1]: {unit}: Control process exited with error code.\n"
        f"Jul 03 10:15:22 {host} systemd[1]: Failed to start {unit.split('.')[0].capitalize()} Service.\n"
    )
    return _make_result(
        exit_code=1,
        stdout=stdout,
        stderr=stderr,
        summary=f"Unit '{unit}' failed to start; the control process exited with an error.",
    )


def _sim_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")

    if _unit_not_found(unit):
        stderr = f"Failed to stop {unit}: Unit {unit} not found.\n"
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be stopped because it was not found.",
        )

    # Not active — systemctl stop on an already-stopped unit exits 0
    active = _unit_is_active(unit, ctx)
    if not active:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"Unit '{unit}' was already inactive; stop command completed without error.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Unit '{unit}' stopped successfully.",
    )


def _sim_restart(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")
    host = _hostname(ctx)

    if _unit_not_found(unit):
        stderr = (
            f"Failed to restart {unit}: Unit {unit} not found.\n"
        )
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be restarted because it was not found.",
        )

    # Hash-based failure scatter for restart (restart is more likely to surface errors)
    h = int(hashlib.md5((unit + "restart").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"Job for {unit} failed because the control process exited with error code.\n"
            f"See 'systemctl status {unit}' and 'journalctl -xeu {unit}' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' failed to restart; check the service configuration for errors.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Unit '{unit}' restarted successfully.",
    )


def _sim_enable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")

    if _unit_not_found(unit):
        stderr = f"Failed to enable {unit}: Unit {unit} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be enabled because it was not found.",
        )

    # Realistic: systemctl enable prints the symlink it creates
    unit_base = unit.split(".")[0]
    stdout = (
        f"Created symlink /etc/systemd/system/multi-user.target.wants/{unit}"
        f" → /usr/lib/systemd/system/{unit}.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Unit '{unit}' enabled to start at boot.",
    )


def _sim_disable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")

    if _unit_not_found(unit):
        stderr = f"Failed to disable {unit}: Unit {unit} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be disabled because it was not found.",
        )

    stdout = (
        f"Removed /etc/systemd/system/multi-user.target.wants/{unit}.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Unit '{unit}' disabled; it will not start automatically at boot.",
    )


def _sim_logs(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")
    lines = int(args.get("lines", 50))
    lines = max(1, min(lines, 500))
    host = _hostname(ctx)

    if _unit_not_found(unit):
        stdout = (
            f"-- No entries --\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"No journal entries found for unit '{unit}'.",
        )

    # Build a plausible journal block
    unit_base = unit.split(".")[0]
    active = _unit_is_active(unit, ctx)
    pid = 1000 + (sum(ord(c) for c in unit) % 8000)

    log_lines: list[str] = [
        f"-- Logs begin at Mon 2026-06-29 00:00:00 UTC, end at Thu 2026-07-03 10:30:00 UTC. --",
        f"Jul 03 00:01:02 {host} systemd[1]: Starting {unit_base.capitalize()} Service...",
        f"Jul 03 00:01:04 {host} systemd[1]: Started {unit_base.capitalize()} Service.",
    ]

    if active:
        log_lines += [
            f"Jul 03 02:15:33 {host} {unit_base}[{pid}]: Configuration reloaded successfully.",
            f"Jul 03 04:00:01 {host} {unit_base}[{pid}]: Routine maintenance cycle complete.",
            f"Jul 03 08:42:11 {host} {unit_base}[{pid}]: Connection from 10.0.1.5 handled.",
            f"Jul 03 09:10:55 {host} {unit_base}[{pid}]: Health check passed.",
        ]
    else:
        log_lines += [
            f"Jul 03 06:30:10 {host} {unit_base}[{pid}]: Received SIGTERM.",
            f"Jul 03 06:30:11 {host} systemd[1]: Stopping {unit_base.capitalize()} Service...",
            f"Jul 03 06:30:12 {host} systemd[1]: {unit}: Deactivated successfully.",
        ]

    # Trim to requested line count (excluding the header)
    body = log_lines[:1] + log_lines[1:lines + 1]
    stdout = "\n".join(body) + "\n"
    line_count = len(body) - 1  # exclude header

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved {line_count} journal lines for unit '{unit}'.",
    )


def _sim_mask(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    unit = args.get("unit", "unknown.service")

    if _unit_not_found(unit):
        stderr = f"Failed to mask {unit}: Unit {unit} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Unit '{unit}' could not be masked because it was not found.",
        )

    # Masking an active unit is a warning but still exits 0
    active = _unit_is_active(unit, ctx)
    stdout = f"Created symlink /etc/systemd/system/{unit} → /dev/null.\n"
    if active:
        stderr = (
            f"Warning: The unit file, source configuration file or drop-ins of {unit} changed on disk.\n"
            f"Run 'systemctl daemon-reload' to reload units.\n"
        )
        summary = f"Unit '{unit}' masked (linked to /dev/null); it is currently running and will not restart after stopping."
    else:
        stderr = ""
        summary = f"Unit '{unit}' masked (linked to /dev/null); it cannot be started until unmasked."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr=stderr,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status": _sim_status,
    "start": _sim_start,
    "stop": _sim_stop,
    "restart": _sim_restart,
    "enable": _sim_enable,
    "disable": _sim_disable,
    "logs": _sim_logs,
    "mask": _sim_mask,
}


def simulate_services(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'services' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 8 real ops declared in the
           services ToolSpec (status, start, stop, restart, enable, disable,
           logs, mask).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_services'/'failed_services' lists.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_services: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
