"""core/tools/firewall.py — firewalld management tool (firewall-cmd).

Supported operations
--------------------
  list             (READ)        — show all settings of the active/given zone.
  get_zones        (READ)        — list the defined zones.
  query            (READ)        — query whether a service is allowed in a zone.
  add_service      (WRITE)       — allow a named service in a zone.
  add_port         (WRITE)       — open a port/protocol in a zone.
  remove_service   (WRITE)       — disallow a named service in a zone.
  remove_port      (WRITE)       — close a port/protocol in a zone.
  reload           (WRITE)       — reload the permanent ruleset.
  set_default_zone (WRITE)       — change the default zone.
  panic_on         (DESTRUCTIVE) — drop ALL traffic (lockout on a remote host).

Permission mapping
------------------
  READ        : list, get_zones, query
  WRITE       : add_service, add_port, remove_service, remove_port, reload,
                set_default_zone
  DESTRUCTIVE : panic_on

  set_default_zone is declared WRITE here, but on a remote SSH host it is a
  lockout risk.  The OpSpec class is ADVISORY only — the gate that actually
  fires is resolved by the EXISTING hardened classifier (permissions.py) on
  the FAITHFUL command line that synthesize_command() renders in repl.py,
  which raises the stakes via ExecContext.remote.  This module never
  classifies, never confirms, never audits (A3 / I3 / I4).

  panic_on is declared DESTRUCTIVE; "firewall-cmd --panic-on" trips the
  classifier's firewall-panic rule -> DESTRUCTIVE -> CONFIRM_TYPED, and REFUSE
  in a non-interactive context.  This is the highest lockout blast radius.

Design rules
------------
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (REPL) resolves the permission gate BEFORE dispatch; this
      module does NOT call permissions.classify() internally.
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.

Subprocess mocking
------------------
  firewall-cmd is ABSENT on the dev/build host.  Every test patches
  ``core.tools.firewall.run_subprocess`` so no real process is launched.
  The tool builds a command vector and calls ``run_subprocess``; it never
  inspects ``sys.platform``.
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
# SELinux hint detection (copied from services.py — AVC denials are likely
# when firewalld policy or labelling blocks a firewall-cmd operation).
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
# Zone flag helper
# ---------------------------------------------------------------------------

def _zone_args(args: dict[str, Any]) -> list[str]:
    """Return ['--zone', <zone>] when a zone operand is present, else []."""
    zone = args.get("zone")
    if zone:
        return ["--zone", str(zone)]
    return []


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --list-all"""
    result = run_subprocess(["firewall-cmd", *_zone_args(args), "--list-all"])
    selinux = _maybe_selinux_hint(result.stderr)
    zone = args.get("zone") or "the active zone"
    if result.ok:
        summary = f"Listed firewall settings for {zone}."
    else:
        summary = f"Failed to list firewall settings (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_get_zones(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd --get-zones"""
    result = run_subprocess(["firewall-cmd", "--get-zones"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = len(result.stdout.split())
        summary = f"Found {count} defined firewall zones."
    else:
        summary = f"Failed to list firewall zones (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_query(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --query-service <service>"""
    service: str = args["service"]
    result = run_subprocess(
        ["firewall-cmd", *_zone_args(args), "--query-service", service]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    # firewall-cmd --query-service exits 0 when the service is allowed, 1 when not.
    if result.ok:
        summary = f"Service '{service}' is allowed in the queried zone."
    else:
        summary = f"Service '{service}' is not allowed in the queried zone."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add_service(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --add-service <service>"""
    service: str = args["service"]
    result = run_subprocess(
        ["firewall-cmd", *_zone_args(args), "--add-service", service]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Allowed service '{service}' in the firewall."
    else:
        summary = f"Failed to allow service '{service}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add_port(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --add-port <port>/<proto>"""
    port: str = args["port"]
    result = run_subprocess(
        ["firewall-cmd", *_zone_args(args), "--add-port", port]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Opened port '{port}' in the firewall."
    else:
        summary = f"Failed to open port '{port}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove_service(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --remove-service <service>"""
    service: str = args["service"]
    result = run_subprocess(
        ["firewall-cmd", *_zone_args(args), "--remove-service", service]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Disallowed service '{service}' in the firewall."
    else:
        summary = f"Failed to disallow service '{service}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove_port(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd [--zone <zone>] --remove-port <port>/<proto>"""
    port: str = args["port"]
    result = run_subprocess(
        ["firewall-cmd", *_zone_args(args), "--remove-port", port]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Closed port '{port}' in the firewall."
    else:
        summary = f"Failed to close port '{port}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_reload(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd --reload"""
    result = run_subprocess(["firewall-cmd", "--reload"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Reloaded the firewall ruleset."
    else:
        summary = f"Failed to reload the firewall ruleset (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_default_zone(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd --set-default-zone <zone>"""
    zone: str = args["zone"]
    result = run_subprocess(["firewall-cmd", "--set-default-zone", zone])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Set the default firewall zone to '{zone}'."
    else:
        summary = f"Failed to set the default zone to '{zone}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_panic_on(args: dict[str, Any]) -> ToolResult:
    """firewall-cmd --panic-on — drops ALL traffic in and out of the host."""
    result = run_subprocess(["firewall-cmd", "--panic-on"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Firewall panic mode is on — all traffic is dropped."
    else:
        summary = f"Failed to turn on firewall panic mode (exit {result.exit_code})."
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
    "list": _op_list,
    "get_zones": _op_get_zones,
    "query": _op_query,
    "add_service": _op_add_service,
    "add_port": _op_add_port,
    "remove_service": _op_remove_service,
    "remove_port": _op_remove_port,
    "reload": _op_reload,
    "set_default_zone": _op_set_default_zone,
    "panic_on": _op_panic_on,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a firewall operation and return a structured ToolResult.

    The caller (REPL) is responsible for resolving the permission gate via the
    hardened classifier and writing the audit record.  This function only runs
    the subprocess and constructs a ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        # Should not happen — ToolRegistry validates ops before calling execute().
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for firewall tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Argument specs
# ---------------------------------------------------------------------------

_ZONE_ARG_OPTIONAL = ArgSpec(
    name="zone",
    type=str,
    required=False,
    description="Firewall zone name (e.g. 'public'). Defaults to the active zone.",
)

_ZONE_ARG_REQUIRED = ArgSpec(
    name="zone",
    type=str,
    required=True,
    description="Firewall zone name to set as the default (e.g. 'public').",
)

_SERVICE_ARG = ArgSpec(
    name="service",
    type=str,
    required=True,
    description="Firewall service name (e.g. 'ssh', 'http').",
)

_PORT_ARG = ArgSpec(
    name="port",
    type=str,
    required=True,
    description="Port and protocol (e.g. '8080/tcp', '53/udp').",
)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

FIREWALL_SPEC = ToolSpec(
    name="firewall",
    description="Manage the host firewall via firewall-cmd.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[_ZONE_ARG_OPTIONAL],
            description="List all settings of a firewall zone.",
        ),
        "get_zones": OpSpec(
            op_name="get_zones",
            permission_class=OpClass.READ,
            args=[],
            description="List the defined firewall zones.",
        ),
        "query": OpSpec(
            op_name="query",
            permission_class=OpClass.READ,
            args=[_SERVICE_ARG, _ZONE_ARG_OPTIONAL],
            description="Query whether a service is allowed in a zone.",
        ),
        "add_service": OpSpec(
            op_name="add_service",
            permission_class=OpClass.WRITE,
            args=[_SERVICE_ARG, _ZONE_ARG_OPTIONAL],
            description="Allow a named service in a zone.",
        ),
        "add_port": OpSpec(
            op_name="add_port",
            permission_class=OpClass.WRITE,
            args=[_PORT_ARG, _ZONE_ARG_OPTIONAL],
            description="Open a port and protocol in a zone.",
        ),
        "remove_service": OpSpec(
            op_name="remove_service",
            permission_class=OpClass.WRITE,
            args=[_SERVICE_ARG, _ZONE_ARG_OPTIONAL],
            description="Disallow a named service in a zone.",
        ),
        "remove_port": OpSpec(
            op_name="remove_port",
            permission_class=OpClass.WRITE,
            args=[_PORT_ARG, _ZONE_ARG_OPTIONAL],
            description="Close a port and protocol in a zone.",
        ),
        "reload": OpSpec(
            op_name="reload",
            permission_class=OpClass.WRITE,
            args=[],
            description="Reload the permanent firewall ruleset.",
        ),
        "set_default_zone": OpSpec(
            op_name="set_default_zone",
            # Advisory WRITE; the classifier raises the stakes on a remote host.
            permission_class=OpClass.WRITE,
            args=[_ZONE_ARG_REQUIRED],
            description="Change the default firewall zone.",
        ),
        "panic_on": OpSpec(
            op_name="panic_on",
            permission_class=OpClass.DESTRUCTIVE,
            args=[],
            description="Turn on firewall panic mode, dropping all traffic.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(FIREWALL_SPEC)
