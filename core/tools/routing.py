"""core/tools/routing.py — IP routing table and policy-rule management via the ip command.

Supported operations
--------------------
  route_show         (READ)        — display the system routing table.
  route_add          (WRITE)       — add a static route to the routing table.
  route_del          (WRITE)       — delete a route (advisory WRITE; the Phase 1
                                     classifier escalates 'ip route del default'
                                     and flush shapes to DESTRUCTIVE — a lockout).
  route_flush        (DESTRUCTIVE) — flush all routes in a routing table.
  policy_rule_show   (READ)        — show IP policy routing rules.
  policy_rule_add    (WRITE)       — add an IP policy routing rule.
  policy_rule_flush  (DESTRUCTIVE) — flush all IP policy routing rules.

Overlap note
------------
  The 'network' tool owns interface/address inspection (ip addr/link) and
  interface up/down (ip link set up/down).  This tool owns the routing TABLE
  and policy RULES (ip route .../ip rule ...) exclusively.  Do NOT expose
  network's interface ops here, and do not re-implement 'network.bring_up'
  or 'network.bring_down'.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection (verbatim from services.py)
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_route_show(args: dict[str, Any]) -> ToolResult:
    """ip route show [table <table>]"""
    table: str = args.get("table") or ""
    cmd = ["ip", "route", "show"]
    if table:
        cmd += ["table", table]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        route_count = len([ln for ln in result.stdout.splitlines() if ln.strip()])
        summary = f"Routing table retrieved; {route_count} route(s) listed."
    else:
        summary = f"Failed to retrieve routing table (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_route_add(args: dict[str, Any]) -> ToolResult:
    """ip route add <dest> [via <gateway>] [dev <dev>] [metric <metric>]"""
    dest: str = args["dest"]
    gateway: str = args.get("gateway") or ""
    dev: str = args.get("dev") or ""
    raw_metric = args.get("metric")
    metric: str = str(raw_metric) if raw_metric is not None else ""
    cmd = ["ip", "route", "add", dest]
    if gateway:
        cmd += ["via", gateway]
    if dev:
        cmd += ["dev", dev]
    if metric:
        cmd += ["metric", metric]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Route to '{dest}' added successfully."
    else:
        summary = f"Failed to add route to '{dest}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_route_del(args: dict[str, Any]) -> ToolResult:
    """ip route del <dest> [via <gateway>] [dev <dev>]

    Advisory class: WRITE. The Phase 1 classifier escalates 'ip route del default'
    and 'ip route flush' shapes to DESTRUCTIVE (lockout risk).
    """
    dest: str = args["dest"]
    gateway: str = args.get("gateway") or ""
    dev: str = args.get("dev") or ""
    cmd = ["ip", "route", "del", dest]
    if gateway:
        cmd += ["via", gateway]
    if dev:
        cmd += ["dev", dev]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Route to '{dest}' deleted."
    else:
        summary = f"Failed to delete route to '{dest}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_route_flush(args: dict[str, Any]) -> ToolResult:
    """ip route flush table <table>

    DESTRUCTIVE: flushes every route in the named table.  Flushing 'main'
    removes all routes and severs network connectivity.
    """
    table: str = args["table"]
    result = run_subprocess(["ip", "route", "flush", "table", table])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"All routes in table '{table}' flushed."
    else:
        summary = f"Failed to flush routing table '{table}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_policy_rule_show(args: dict[str, Any]) -> ToolResult:
    """ip rule show"""
    result = run_subprocess(["ip", "rule", "show"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        rule_count = len([ln for ln in result.stdout.splitlines() if ln.strip()])
        summary = f"Policy routing rules retrieved; {rule_count} rule(s) listed."
    else:
        summary = f"Failed to retrieve policy routing rules (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_policy_rule_add(args: dict[str, Any]) -> ToolResult:
    """ip rule add [from <src>] [to <dest>] [priority <prio>] [table <table>]"""
    src: str = args.get("src") or ""
    dest: str = args.get("dest") or ""
    raw_priority = args.get("priority")
    priority: str = str(raw_priority) if raw_priority is not None else ""
    table: str = args.get("table") or ""
    cmd = ["ip", "rule", "add"]
    if src:
        cmd += ["from", src]
    if dest:
        cmd += ["to", dest]
    if priority:
        cmd += ["priority", priority]
    if table:
        cmd += ["table", table]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Policy routing rule added."
    else:
        summary = f"Failed to add policy routing rule (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_policy_rule_flush(args: dict[str, Any]) -> ToolResult:
    """ip rule flush

    DESTRUCTIVE: removes all policy routing rules, which can break routing
    and sever remote access.
    """
    result = run_subprocess(["ip", "rule", "flush"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "All policy routing rules flushed."
    else:
        summary = f"Failed to flush policy routing rules (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "route_show": _op_route_show,
    "route_add": _op_route_add,
    "route_del": _op_route_del,
    "route_flush": _op_route_flush,
    "policy_rule_show": _op_policy_rule_show,
    "policy_rule_add": _op_policy_rule_add,
    "policy_rule_flush": _op_policy_rule_flush,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a routing operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9): unknown ops and all subprocess failures
    return a well-formed ToolResult with a non-zero exit code.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for routing tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_DEST_ARG = ArgSpec(
    name="dest",
    type=str,
    required=True,
    description="Destination network or host (e.g. '192.168.1.0/24', 'default').",
)

ROUTING_SPEC = ToolSpec(
    name="routing",
    description="Manage IP routing table entries and policy routing rules via the ip command.",
    ops={
        "route_show": OpSpec(
            op_name="route_show",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="table",
                    type=str,
                    required=False,
                    description="Routing table name or number (e.g. 'main', 'local', '100'); omit for default.",
                    default=None,
                ),
            ],
            description="Show the system routing table (optionally filtered to a named table).",
        ),
        "route_add": OpSpec(
            op_name="route_add",
            permission_class=OpClass.WRITE,
            args=[
                _DEST_ARG,
                ArgSpec(
                    name="gateway",
                    type=str,
                    required=False,
                    description="Next-hop gateway address (e.g. '10.0.0.1').",
                    default=None,
                ),
                ArgSpec(
                    name="dev",
                    type=str,
                    required=False,
                    description="Output network interface (e.g. 'eth0').",
                    default=None,
                ),
                ArgSpec(
                    name="metric",
                    type=int,
                    required=False,
                    description="Route metric; lower value is preferred.",
                    default=None,
                ),
            ],
            description="Add a static route to the routing table.",
        ),
        "route_del": OpSpec(
            op_name="route_del",
            permission_class=OpClass.WRITE,
            args=[
                _DEST_ARG,
                ArgSpec(
                    name="gateway",
                    type=str,
                    required=False,
                    description="Next-hop gateway to match when deleting (optional).",
                    default=None,
                ),
                ArgSpec(
                    name="dev",
                    type=str,
                    required=False,
                    description="Interface to match when deleting (optional).",
                    default=None,
                ),
            ],
            description=(
                "Delete a route from the routing table. "
                "Deleting the default route or flushing routes severs connectivity."
            ),
        ),
        "route_flush": OpSpec(
            op_name="route_flush",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="table",
                    type=str,
                    required=True,
                    description="Routing table to flush (e.g. 'main', '100').",
                ),
            ],
            description=(
                "Flush all routes from a routing table. "
                "Flushing 'main' removes all routes and severs network connectivity."
            ),
        ),
        "policy_rule_show": OpSpec(
            op_name="policy_rule_show",
            permission_class=OpClass.READ,
            args=[],
            description="Show all IP policy routing rules (ip rule show).",
        ),
        "policy_rule_add": OpSpec(
            op_name="policy_rule_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="src",
                    type=str,
                    required=False,
                    description="Source address prefix the rule matches (e.g. '10.1.0.0/24').",
                    default=None,
                ),
                ArgSpec(
                    name="dest",
                    type=str,
                    required=False,
                    description="Destination address prefix the rule matches.",
                    default=None,
                ),
                ArgSpec(
                    name="priority",
                    type=int,
                    required=False,
                    description="Rule priority (lower number = higher priority).",
                    default=None,
                ),
                ArgSpec(
                    name="table",
                    type=str,
                    required=False,
                    description="Routing table to use when this rule matches.",
                    default=None,
                ),
            ],
            description="Add an IP policy routing rule.",
        ),
        "policy_rule_flush": OpSpec(
            op_name="policy_rule_flush",
            permission_class=OpClass.DESTRUCTIVE,
            args=[],
            description=(
                "Flush all IP policy routing rules. "
                "Removing all rules can break routing and sever remote access."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(ROUTING_SPEC)
