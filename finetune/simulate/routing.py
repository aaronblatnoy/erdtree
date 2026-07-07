"""finetune/simulate/routing.py — Rocky Linux 9 output simulator for the 'routing' tool.

Public API
----------
simulate_routing(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/routing.py
    args : dict of op arguments (may be {} for all-optional ops; defaults applied)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real 'ip' command behaviour:
    0  — success
    1  — general error (route already exists, no such route, permission denied)
    2  — usage error (bad arguments)
  127  — binary not found (ip command missing)
* stdout/stderr reflect the actual 'ip route show' and 'ip rule show' output
  format on Rocky Linux 9 (iproute2 package).
* Failure triggers are deterministic via hash-based scatter so traces teach
  error handling without requiring the binary to be present.

I2 compliance
-------------
All `summary` strings are I2-clean (no AI/LLM/model/agent/inference language).

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (avoids circular imports when the
Phase-13 __init__.py imports simulators before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
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


def _route_exists(dest: str) -> bool:
    """Deterministically decide if a route destination looks valid/present."""
    lower = dest.lower()
    for tok in ("notfound", "noexist", "bogus", "missing", "invalid"):
        if tok in lower:
            return False
    # Hash scatter: ~15% failure rate for variety
    h = int(hashlib.md5(dest.encode()).hexdigest(), 16)
    return h % 7 != 0


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

def _sim_route_show(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    table = args.get("table") or ""
    host = _hostname(ctx)

    # Realistic iproute2 output for 'ip route show'
    if table and table not in ("main", "local", "default", "all") and not table.isdigit():
        stderr = f"Error: ipv4: FIB table does not exist.\nDump terminated\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Routing table '{table}' does not exist or is not accessible.",
        )

    table_label = f" (table {table})" if table else ""
    stdout = (
        "default via 10.0.0.1 dev eth0 proto dhcp metric 100 \n"
        "10.0.0.0/8 dev eth0 proto kernel scope link src 10.0.0.5 \n"
        "172.16.0.0/16 via 10.0.0.254 dev eth0 metric 200 \n"
        "192.168.100.0/24 dev eth1 proto kernel scope link src 192.168.100.1 \n"
    )
    route_count = len([ln for ln in stdout.splitlines() if ln.strip()])
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Routing table{table_label} retrieved; {route_count} route(s) listed.",
    )


def _sim_route_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dest = args.get("dest", "192.168.99.0/24")
    gateway = args.get("gateway") or ""
    dev = args.get("dev") or ""

    # Simulate RTNETLINK error if dest looks malformed
    h = int(hashlib.md5((dest + "add").encode()).hexdigest(), 16)
    if h % 9 == 0:
        stderr = "Error: any valid prefix is expected rather than possibly valid prefix.\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add route to '{dest}' — invalid prefix or duplicate route.",
        )

    # Check for duplicate (already exists)
    if not _route_exists(dest) or h % 13 == 0:
        stderr = "RTNETLINK answers: File exists\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add route to '{dest}' (exit 2) — route already exists.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Route to '{dest}' added successfully.",
    )


def _sim_route_del(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dest = args.get("dest", "192.168.99.0/24")

    if not _route_exists(dest):
        stderr = "RTNETLINK answers: No such process\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to delete route to '{dest}' — no matching route found.",
        )

    # Warn context: deleting default is high-risk
    if dest.lower() == "default":
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Default route deleted; all traffic via the removed gateway is now unreachable.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Route to '{dest}' deleted.",
    )


def _sim_route_flush(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    table = args.get("table", "main")

    if table not in ("main", "local", "default", "all") and not table.isdigit():
        stderr = f"Error: ipv4: FIB table does not exist.\nDump terminated\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to flush routing table '{table}' — table not found (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"All routes in table '{table}' flushed.",
    )


def _sim_policy_rule_show(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Realistic 'ip rule show' output (iproute2 format)
    stdout = (
        "0:\tfrom all lookup local\n"
        "32766:\tfrom all lookup main\n"
        "32767:\tfrom all lookup default\n"
    )
    rule_count = len([ln for ln in stdout.splitlines() if ln.strip()])
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Policy routing rules retrieved; {rule_count} rule(s) listed.",
    )


def _sim_policy_rule_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    src = args.get("src") or ""
    dest = args.get("dest") or ""
    priority = args.get("priority")
    table = args.get("table") or ""

    # Simulate conflict: rule already exists
    key = f"{src}{dest}{priority}{table}"
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    if h % 11 == 0:
        stderr = "RTNETLINK answers: File exists\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary="Failed to add policy routing rule (exit 2) — duplicate rule.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Policy routing rule added.",
    )


def _sim_policy_rule_flush(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="All policy routing rules flushed.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "route_show": _sim_route_show,
    "route_add": _sim_route_add,
    "route_del": _sim_route_del,
    "route_flush": _sim_route_flush,
    "policy_rule_show": _sim_policy_rule_show,
    "policy_rule_add": _sim_policy_rule_add,
    "policy_rule_flush": _sim_policy_rule_flush,
}


def simulate_routing(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'routing' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in the
           routing ToolSpec.
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

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
            f"simulate_routing: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
