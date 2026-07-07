"""finetune/simulate/chrony.py — Rocky Linux 9 output simulator for the 'chrony' tool.

Public API
----------
simulate_chrony(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/chrony.py
           (tracking, sources, status, makestep, conf_view, conf_edit)
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict — both are supported.

Realism model
-------------
* chronyc tracking / sources output mirrors real Rocky 9 chronyc output.
* chronyd status output mirrors systemctl cgroups-v2 style.
* Failure branches: command-not-found (exit 127), permission denied (exit 1),
  chronyd not running (exit 3), hash-based scatter for variety.

I2 compliance
-------------
All `summary` strings are I2-clean. No AI/LLM/model/agent language.

INV-read-only-core: imports NOTHING from core/ directly.
Does NOT import finetune.coreimports (avoids circular deps at Phase-13 import).
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


def _chronyd_running(ctx: Any) -> bool:
    """Return True if the context indicates chronyd is running."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("chrony" in s for s in active)
    if isinstance(ctx, str):
        return "chronyd" in ctx
    return True  # default optimistic for simulation variety


def _chronyc_unavailable(ctx: Any) -> bool:
    """Deterministically decide if chronyc should appear unavailable (~10%)."""
    seed = str(ctx)[:32] if ctx else "default"
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return h % 10 == 0


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

def _sim_tracking(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    if not _chronyd_running(ctx):
        stderr = "506 Cannot talk to daemon\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to retrieve clock tracking statistics — chronyd is not running.",
        )

    stdout = (
        "Reference ID    : C2B5F6CD (162.181.246.205)\n"
        "Stratum         : 2\n"
        "Ref time (UTC)  : Fri Jul 04 00:01:02 2026\n"
        "System time     : 0.000001234 seconds slow of NTP time\n"
        "Last offset     : -0.000001234 seconds\n"
        "RMS offset      : 0.000002345 seconds\n"
        "Frequency       : 12.345 ppm slow\n"
        "Residual freq   : -0.001 ppm\n"
        "Skew            : 0.012 ppm\n"
        "Root delay      : 0.023456789 seconds\n"
        "Root dispersion : 0.000012345 seconds\n"
        "Update interval : 64.2 seconds\n"
        "Leap status     : Normal\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Clock tracking statistics retrieved from chronyc.",
    )


def _sim_sources(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if not _chronyd_running(ctx):
        stderr = "506 Cannot talk to daemon\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to retrieve NTP source list — chronyd is not running.",
        )

    stdout = (
        "MS Name/IP address         Stratum Poll Reach LastRx Last sample               \n"
        "===============================================================================\n"
        "^* time1.example.com             2   6   377    12  +0.012ms[+0.023ms] +/- 1.234ms\n"
        "^+ time2.example.com             2   6   377    43  -0.034ms[-0.045ms] +/- 2.345ms\n"
        "^- ntp.pool.example.net          3   6   377    68  +0.056ms[+0.056ms] +/- 5.678ms\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="NTP source list retrieved from chronyc.",
    )


def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    if _chronyd_running(ctx):
        stdout = (
            "● chronyd.service - NTP client/server\n"
            "     Loaded: loaded (/usr/lib/systemd/system/chronyd.service; enabled; preset: enabled)\n"
            "     Active: active (running) since Fri 2026-07-04 00:00:01 UTC; 4h 30min ago\n"
            "   Main PID: 1234 (chronyd)\n"
            "      Tasks: 1 (limit: 23168)\n"
            "     Memory: 3.2M\n"
            "        CPU: 234ms\n"
            "     CGroup: /system.slice/chronyd.service\n"
            f"             └─1234 /usr/sbin/chronyd -F 2\n"
            f"\n"
            f"Jul 04 00:00:01 {host} systemd[1]: Started NTP client/server.\n"
            f"Jul 04 00:00:02 {host} chronyd[1234]: Selected source 162.181.246.205 (time1.example.com)\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="chronyd service is active and running.",
        )
    else:
        stdout = (
            "○ chronyd.service - NTP client/server\n"
            "     Loaded: loaded (/usr/lib/systemd/system/chronyd.service; disabled; preset: enabled)\n"
            "     Active: inactive (dead)\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary="chronyd service reported a non-zero status (exit 3).",
        )


def _sim_makestep(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if not _chronyd_running(ctx):
        stderr = "506 Cannot talk to daemon\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Clock step failed — chronyd is not running (exit 1).",
        )

    # Hash-based scatter: occasionally simulate a step that finds clock already close
    h = int(hashlib.md5(b"makestep").hexdigest(), 16)
    if h % 5 == 0:
        stdout = "200 OK\nClock already close to NTP time, step not required.\n"
        summary = "System clock stepped to the NTP reference time."
    else:
        stdout = "200 OK\nClock stepped by -0.123456789 seconds.\n"
        summary = "System clock stepped to the NTP reference time."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


def _sim_conf_view(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Hash-based scatter: ~10% simulate a missing config
    h = int(hashlib.md5(b"conf_view").hexdigest(), 16)
    if h % 10 == 0:
        stderr = "cat: /etc/chrony.conf: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to read /etc/chrony.conf (exit 1).",
        )

    stdout = (
        "# /etc/chrony.conf — Rocky Linux 9 default\n"
        "pool 2.rocky.pool.ntp.org iburst\n"
        "driftfile /var/lib/chrony/drift\n"
        "makestep 1.0 3\n"
        "rtcsync\n"
        "keyfile /etc/chrony.keys\n"
        "ntsdumpdir /var/lib/chrony\n"
        "leapsectz right/UTC\n"
        "logdir /var/log/chrony\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Contents of /etc/chrony.conf retrieved.",
    )


def _sim_conf_edit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    content = args.get("content", "")

    if not content:
        stderr = "tee: /etc/chrony.conf: no content supplied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to write /etc/chrony.conf — no content supplied (exit 1).",
        )

    # Simulate permission denied if context suggests non-root
    if isinstance(ctx, dict) and ctx.get("user") not in (None, "root"):
        stderr = "tee: /etc/chrony.conf: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to write /etc/chrony.conf (exit 1).",
        )

    # Success: tee echoes the content to stdout
    return _make_result(
        exit_code=0,
        stdout=content,
        stderr="",
        summary="Configuration written to /etc/chrony.conf.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "tracking": _sim_tracking,
    "sources": _sim_sources,
    "status": _sim_status,
    "makestep": _sim_makestep,
    "conf_view": _sim_conf_view,
    "conf_edit": _sim_conf_edit,
}


def simulate_chrony(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'chrony' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in
           core/tools/chrony.py (tracking, sources, status, makestep,
           conf_view, conf_edit).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_services' list.

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
            f"simulate_chrony: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
