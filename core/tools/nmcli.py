"""core/tools/nmcli.py — NetworkManager connection-profile management via nmcli.

Supported operations
--------------------
  device_status    (READ)        — show NM device and connection overview.
  connection_show  (READ)        — show details of a named connection profile.
  connection_add   (WRITE)       — create a new connection profile.
  connection_modify(WRITE)       — modify a property of an existing profile.
  connection_up    (WRITE)       — activate a connection profile on its interface.
  connection_down  (WRITE)       — deactivate a connection profile.
  connection_delete(DESTRUCTIVE) — permanently delete a connection profile.
  wifi_list        (READ)        — list visible Wi-Fi access points.
  wifi_connect     (WRITE)       — connect to a Wi-Fi network by SSID.
  dns_configure    (WRITE)       — set DNS servers on a connection profile.

Scope / overlap notes:
  This tool manages NetworkManager connection PROFILES via nmcli.
  It does NOT re-expose network.py's interface link up/down (ip link set)
  or network.py's set_ip (which also wraps nmcli con modify ipv4.addresses).
  connection_modify is the broader profile-property setter; set_ip in
  network.py remains the authoritative IP-assignment convenience op.
  DNS profile writes live here (dns_configure); DNS lookups/diagnostics
  live in the dns tool.
  wifi_list scans available networks; network.wifi reports the connected
  SSID — the two are complementary, not duplicates.

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
# SELinux hint detection
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

def _op_device_status(args: dict[str, Any]) -> ToolResult:
    """nmcli device status"""
    result = run_subprocess(["nmcli", "device", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NetworkManager device status retrieved."
    else:
        summary = f"Failed to retrieve device status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_show(args: dict[str, Any]) -> ToolResult:
    """nmcli connection show <name>"""
    name: str = args["name"]
    result = run_subprocess(["nmcli", "connection", "show", name])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Connection profile '{name}' details retrieved."
    else:
        summary = (
            f"Connection profile '{name}' not found or could not be shown "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_add(args: dict[str, Any]) -> ToolResult:
    """nmcli connection add type <type> con-name <name> ifname <ifname> [ip4 ...] [gw4 ...]"""
    con_type: str = args["type"]
    con_name: str = args["con_name"]
    ifname: str = args["ifname"]
    cmd = [
        "nmcli", "connection", "add",
        "type", con_type,
        "con-name", con_name,
        "ifname", ifname,
    ]
    ip4: str | None = args.get("ip4")
    gw4: str | None = args.get("gw4")
    if ip4:
        cmd += ["ip4", ip4]
    if gw4:
        cmd += ["gw4", gw4]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Connection profile '{con_name}' of type '{con_type}' "
            f"created on interface '{ifname}'."
        )
    else:
        summary = (
            f"Failed to create connection profile '{con_name}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_modify(args: dict[str, Any]) -> ToolResult:
    """nmcli connection modify <name> <property> <value>"""
    name: str = args["name"]
    prop: str = args["property"]
    value: str = args["value"]
    result = run_subprocess(["nmcli", "connection", "modify", name, prop, value])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Connection profile '{name}': property '{prop}' set to '{value}'."
        )
    else:
        summary = (
            f"Failed to modify connection profile '{name}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_up(args: dict[str, Any]) -> ToolResult:
    """nmcli connection up <name>"""
    name: str = args["name"]
    result = run_subprocess(["nmcli", "connection", "up", name])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Connection profile '{name}' activated."
    else:
        summary = (
            f"Failed to activate connection profile '{name}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_down(args: dict[str, Any]) -> ToolResult:
    """nmcli connection down <name>"""
    name: str = args["name"]
    result = run_subprocess(["nmcli", "connection", "down", name])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Connection profile '{name}' deactivated."
    else:
        summary = (
            f"Failed to deactivate connection profile '{name}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connection_delete(args: dict[str, Any]) -> ToolResult:
    """nmcli connection delete <name>"""
    name: str = args["name"]
    result = run_subprocess(["nmcli", "connection", "delete", name])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Connection profile '{name}' deleted."
    else:
        summary = (
            f"Failed to delete connection profile '{name}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_wifi_list(args: dict[str, Any]) -> ToolResult:
    """nmcli device wifi list [ifname <ifname>]"""
    cmd = ["nmcli", "device", "wifi", "list"]
    ifname: str | None = args.get("ifname")
    if ifname:
        cmd += ["ifname", ifname]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Available Wi-Fi networks retrieved."
    else:
        summary = f"Failed to list Wi-Fi networks (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_wifi_connect(args: dict[str, Any]) -> ToolResult:
    """nmcli device wifi connect <ssid> [password <password>]"""
    ssid: str = args["ssid"]
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    password: str | None = args.get("password")
    if password:
        cmd += ["password", password]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Connected to Wi-Fi network '{ssid}'."
    else:
        summary = f"Failed to connect to Wi-Fi network '{ssid}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dns_configure(args: dict[str, Any]) -> ToolResult:
    """nmcli connection modify <name> ipv4.dns <dns>"""
    name: str = args["name"]
    dns: str = args["dns"]
    result = run_subprocess(["nmcli", "connection", "modify", name, "ipv4.dns", dns])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"DNS servers for connection profile '{name}' set to '{dns}'."
    else:
        summary = (
            f"Failed to configure DNS on connection profile '{name}' "
            f"(exit {result.exit_code})."
        )
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
    "device_status":    _op_device_status,
    "connection_show":  _op_connection_show,
    "connection_add":   _op_connection_add,
    "connection_modify": _op_connection_modify,
    "connection_up":    _op_connection_up,
    "connection_down":  _op_connection_down,
    "connection_delete": _op_connection_delete,
    "wifi_list":        _op_wifi_list,
    "wifi_connect":     _op_wifi_connect,
    "dns_configure":    _op_dns_configure,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an nmcli operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record.  This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for nmcli tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_NAME_ARG = ArgSpec(
    name="name",
    type=str,
    required=True,
    description="Connection profile name (as shown by 'nmcli connection show').",
)

NMCLI_SPEC = ToolSpec(
    name="nmcli",
    description="Manage NetworkManager connection profiles via nmcli.",
    ops={
        "device_status": OpSpec(
            op_name="device_status",
            permission_class=OpClass.READ,
            args=[],
            description="Show NetworkManager device and connection state for all interfaces.",
        ),
        "connection_show": OpSpec(
            op_name="connection_show",
            permission_class=OpClass.READ,
            args=[_NAME_ARG],
            description="Show detailed settings for a named connection profile.",
        ),
        "connection_add": OpSpec(
            op_name="connection_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="type",
                    type=str,
                    required=True,
                    description="Connection type (e.g. 'ethernet', 'wifi', 'bond').",
                ),
                ArgSpec(
                    name="con_name",
                    type=str,
                    required=True,
                    description="Name to assign to the new connection profile.",
                ),
                ArgSpec(
                    name="ifname",
                    type=str,
                    required=True,
                    description="Interface name to bind the connection to (e.g. 'eth0').",
                ),
                ArgSpec(
                    name="ip4",
                    type=str,
                    required=False,
                    description="IPv4 address with prefix (e.g. '192.168.1.10/24').",
                    default=None,
                ),
                ArgSpec(
                    name="gw4",
                    type=str,
                    required=False,
                    description="IPv4 default gateway (e.g. '192.168.1.1').",
                    default=None,
                ),
            ],
            description="Create a new NetworkManager connection profile.",
        ),
        "connection_modify": OpSpec(
            op_name="connection_modify",
            permission_class=OpClass.WRITE,
            args=[
                _NAME_ARG,
                ArgSpec(
                    name="property",
                    type=str,
                    required=True,
                    description="NM property to set (e.g. 'ipv4.addresses', 'connection.autoconnect').",
                ),
                ArgSpec(
                    name="value",
                    type=str,
                    required=True,
                    description="Value to assign to the property.",
                ),
            ],
            description="Modify a property of an existing connection profile.",
        ),
        "connection_up": OpSpec(
            op_name="connection_up",
            permission_class=OpClass.WRITE,
            args=[_NAME_ARG],
            description="Activate (bring up) a connection profile on its bound interface.",
        ),
        "connection_down": OpSpec(
            op_name="connection_down",
            permission_class=OpClass.WRITE,
            args=[_NAME_ARG],
            description="Deactivate (bring down) a connection profile.",
        ),
        "connection_delete": OpSpec(
            op_name="connection_delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_NAME_ARG],
            description=(
                "Permanently delete a connection profile — cannot be undone "
                "and may sever network access if the profile is currently active."
            ),
        ),
        "wifi_list": OpSpec(
            op_name="wifi_list",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="ifname",
                    type=str,
                    required=False,
                    description="Restrict scan to this Wi-Fi interface (e.g. 'wlan0').",
                    default=None,
                ),
            ],
            description="List available Wi-Fi access points visible to the system.",
        ),
        "wifi_connect": OpSpec(
            op_name="wifi_connect",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="ssid",
                    type=str,
                    required=True,
                    description="SSID of the Wi-Fi network to join.",
                ),
                ArgSpec(
                    name="password",
                    type=str,
                    required=False,
                    description="Wi-Fi passphrase (omit for open networks).",
                    default=None,
                ),
            ],
            description="Connect to a Wi-Fi network by SSID.",
        ),
        "dns_configure": OpSpec(
            op_name="dns_configure",
            permission_class=OpClass.WRITE,
            args=[
                _NAME_ARG,
                ArgSpec(
                    name="dns",
                    type=str,
                    required=True,
                    description=(
                        "Space-separated DNS server addresses to set on the profile "
                        "(e.g. '8.8.8.8 8.8.4.4')."
                    ),
                ),
            ],
            description="Set DNS servers on a connection profile via nmcli.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(NMCLI_SPEC)
