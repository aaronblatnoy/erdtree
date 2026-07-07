"""core/tools/dns.py — DNS inspection and cache management via system DNS utilities.

Supported operations
--------------------
  resolv_view   (READ)  — display the contents of /etc/resolv.conf.
  named_status  (READ)  — show the systemctl status of the named (BIND) service.
  dig           (READ)  — perform a DNS lookup via the dig utility.
  nslookup      (READ)  — perform a DNS lookup via nslookup.
  host          (READ)  — perform a DNS lookup via the host utility.
  flush_caches  (WRITE) — flush the local DNS resolver cache via resolvectl.

Permission mapping (advisory, per the Phase 4 plan table):
  READ  : resolv_view, named_status, dig, nslookup, host
  WRITE : flush_caches

Overlap notes (from OVERLAP-MAP.md):
  dns vs network/nmcli — the dns tool is scoped to inspection/diagnostics and
  cache flush ONLY. Writing DNS configuration into a NetworkManager connection
  profile is the domain of the nmcli tool. Do not add any profile-write op here.

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

def _op_resolv_view(args: dict[str, Any]) -> ToolResult:
    """Display /etc/resolv.conf — shows configured nameservers and search domains."""
    result = run_subprocess(["cat", "/etc/resolv.conf"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Read /etc/resolv.conf successfully."
    else:
        summary = f"Failed to read /etc/resolv.conf (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_named_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status --no-pager named — check BIND/named service state."""
    result = run_subprocess(["systemctl", "status", "--no-pager", "named"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "The named service is active and running."
    else:
        summary = f"The named service reported status exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dig(args: dict[str, Any]) -> ToolResult:
    """dig [+noall +answer] [@server] <name> [type] — DNS record lookup via dig."""
    name: str = args["name"]
    record_type: str = args.get("record_type") or "A"
    server: str = args.get("server") or ""

    cmd = ["dig", "+noall", "+answer"]
    if server:
        cmd.append(f"@{server}")
    cmd.append(name)
    cmd.append(record_type)

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"DNS lookup for '{name}' ({record_type}) completed."
    else:
        summary = f"DNS lookup for '{name}' ({record_type}) failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_nslookup(args: dict[str, Any]) -> ToolResult:
    """nslookup <name> [server] — DNS lookup via nslookup."""
    name: str = args["name"]
    server: str = args.get("server") or ""

    cmd = ["nslookup", name]
    if server:
        cmd.append(server)

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"nslookup for '{name}' returned results."
    else:
        summary = f"nslookup for '{name}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_host(args: dict[str, Any]) -> ToolResult:
    """host <name> [server] — DNS lookup via host utility."""
    name: str = args["name"]
    server: str = args.get("server") or ""

    cmd = ["host", name]
    if server:
        cmd.append(server)

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"host lookup for '{name}' returned results."
    else:
        summary = f"host lookup for '{name}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_flush_caches(args: dict[str, Any]) -> ToolResult:
    """resolvectl flush-caches — flush the local DNS resolver cache."""
    result = run_subprocess(["resolvectl", "flush-caches"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "DNS resolver cache flushed successfully."
    else:
        summary = f"Failed to flush DNS resolver cache (exit {result.exit_code})."
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
    "resolv_view":  _op_resolv_view,
    "named_status": _op_named_status,
    "dig":          _op_dig,
    "nslookup":     _op_nslookup,
    "host":         _op_host,
    "flush_caches": _op_flush_caches,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a dns operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9): unknown ops and missing binaries
    (exit 127) both degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for dns tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Shared ArgSpecs
# ---------------------------------------------------------------------------

_NAME_ARG = ArgSpec(
    name="name",
    type=str,
    required=True,
    description="Hostname or IP address to look up.",
)

_SERVER_ARG = ArgSpec(
    name="server",
    type=str,
    required=False,
    description="DNS server to query (optional; uses system resolver if omitted).",
    default=None,
)

_RECORD_TYPE_ARG = ArgSpec(
    name="record_type",
    type=str,
    required=False,
    description="DNS record type to query (e.g. A, AAAA, MX, TXT, CNAME; default: A).",
    default="A",
)

# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

DNS_SPEC = ToolSpec(
    name="dns",
    description=(
        "Inspect DNS configuration and perform record lookups via dig, nslookup, "
        "and host; view /etc/resolv.conf; check the named service; flush the local "
        "resolver cache."
    ),
    ops={
        "resolv_view": OpSpec(
            op_name="resolv_view",
            permission_class=OpClass.READ,
            args=[],
            description="Display /etc/resolv.conf to show configured nameservers and search domains.",
        ),
        "named_status": OpSpec(
            op_name="named_status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the named (BIND) DNS service via systemctl.",
        ),
        "dig": OpSpec(
            op_name="dig",
            permission_class=OpClass.READ,
            args=[_NAME_ARG, _RECORD_TYPE_ARG, _SERVER_ARG],
            description="Perform a DNS record lookup using dig.",
        ),
        "nslookup": OpSpec(
            op_name="nslookup",
            permission_class=OpClass.READ,
            args=[_NAME_ARG, _SERVER_ARG],
            description="Perform a DNS lookup using nslookup.",
        ),
        "host": OpSpec(
            op_name="host",
            permission_class=OpClass.READ,
            args=[_NAME_ARG, _SERVER_ARG],
            description="Perform a DNS lookup using the host utility.",
        ),
        "flush_caches": OpSpec(
            op_name="flush_caches",
            permission_class=OpClass.WRITE,
            args=[],
            description="Flush the local DNS resolver cache via resolvectl flush-caches.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(DNS_SPEC)
