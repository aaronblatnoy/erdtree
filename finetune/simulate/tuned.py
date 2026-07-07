"""finetune/simulate/tuned.py — Rocky Linux 9 output simulator for the 'tuned' tool.

Public API
----------
simulate_tuned(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/tuned.py
           (list, active, recommend, profile, off)
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real tuned-adm behaviour:
    0  — success
    1  — operation failed (profile not found, tuned daemon not running, etc.)
* stdout reflects Rocky 9 tuned-adm output format (profile lists, active lines).
* Failure branches are deterministic: a profile name containing "notfound",
  "bogus", "missing", or "invalid" triggers a not-found error; a hash-based
  ~15% scatter adds variety among otherwise valid-looking profile names.
* ctx is inspected to seed the currently-active profile name.

I2 compliance
-------------
All summary strings are I2-clean. No forbidden terms appear anywhere.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Known Rocky 9 tuned profiles (realistic corpus)
# ---------------------------------------------------------------------------

_KNOWN_PROFILES: list[str] = [
    "accelerator-performance",
    "balanced",
    "cpu-partitioning",
    "desktop",
    "hpc-compute",
    "intel-sst",
    "latency-performance",
    "mssql",
    "network-latency",
    "network-throughput",
    "optimize-serial-console",
    "oracle",
    "postgresql",
    "powersave",
    "realtime",
    "realtime-virtual-guest",
    "realtime-virtual-host",
    "throughput-performance",
    "virtual-guest",
    "virtual-host",
]

_DEFAULT_ACTIVE_PROFILE = "throughput-performance"
_DEFAULT_RECOMMENDED_PROFILE = "throughput-performance"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _active_profile(ctx: Any) -> str:
    """Return the currently active profile from ctx, or the default."""
    if isinstance(ctx, dict):
        return ctx.get("tuned_profile", _DEFAULT_ACTIVE_PROFILE)
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if "tuned" in line.lower() and "profile" in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    candidate = parts[1].strip()
                    if candidate:
                        return candidate
    return _DEFAULT_ACTIVE_PROFILE


def _profile_not_found(profile: str) -> bool:
    """Deterministically decide if a profile name should trigger a not-found error."""
    lower = profile.lower()
    for tok in ("notfound", "bogus", "missing", "invalid", "noexist", "broken", "fail"):
        if tok in lower:
            return True
    # Hash-based deterministic scatter (~15%) for names not in known list
    if profile not in _KNOWN_PROFILES:
        h = int(hashlib.md5(profile.encode()).hexdigest(), 16)
        return h % 7 == 0
    return False


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

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tuned-adm list"""
    active = _active_profile(ctx)

    lines = ["Available profiles:"]
    for p in _KNOWN_PROFILES:
        if p == active:
            lines.append(f"- {p} (active)")
        else:
            lines.append(f"- {p}")
    lines.append(f"Current active profile: {active}")
    stdout = "\n".join(lines) + "\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Available tuned profiles listed successfully.",
    )


def _sim_active(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tuned-adm active"""
    active = _active_profile(ctx)

    # Simulate tuned daemon not running on hash-based scatter (~10%)
    h = int(hashlib.md5(b"active-check").hexdigest(), 16)
    if isinstance(ctx, dict) and not ctx.get("tuned_running", True):
        stderr = "No current active profile.\nIt seems that tuned daemon is not running, preset is not activated.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="No active tuned profile; the tuned service may not be running.",
        )

    stdout = f"Current active profile: {active}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Currently active tuned profile is '{active}'.",
    )


def _sim_recommend(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tuned-adm recommend"""
    if isinstance(ctx, dict):
        recommended = ctx.get("tuned_recommended", _DEFAULT_RECOMMENDED_PROFILE)
    else:
        recommended = _DEFAULT_RECOMMENDED_PROFILE

    stdout = f"{recommended}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Recommended tuned profile for this system is '{recommended}'.",
    )


def _sim_profile(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tuned-adm profile <name>"""
    profile = args.get("profile", "balanced")

    if _profile_not_found(profile):
        stderr = f"tuned-adm: error: Unable to switch profile, unknown profile: {profile}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to switch tuned profile; '{profile}' is not a recognised profile name.",
        )

    stdout = f"Switching to profile '{profile}'\nSwitched to profile '{profile}'\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Tuned profile switched to '{profile}'.",
    )


def _sim_off(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tuned-adm off"""
    # Simulate failure if tuned daemon is explicitly marked not running
    if isinstance(ctx, dict) and not ctx.get("tuned_running", True):
        stderr = "tuned-adm: error: Failed to communicate with tuned: Failed to communicate with tuned daemon.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to deactivate tuned profile; the tuned service may not be running.",
        )

    stdout = "Turned off tuning.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Tuned profile deactivated; no profile is now active.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":      _sim_list,
    "active":    _sim_active,
    "recommend": _sim_recommend,
    "profile":   _sim_profile,
    "off":       _sim_off,
}


def simulate_tuned(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'tuned' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 5 real ops declared in the
           tuned ToolSpec (list, active, recommend, profile, off).
    args : argument dict (may be {} for ops with no required args).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with optional keys 'tuned_profile',
           'tuned_recommended', 'tuned_running', 'hostname'.

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
            f"simulate_tuned: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
