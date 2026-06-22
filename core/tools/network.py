"""core/tools/network.py — Network interface and connection management.

Supported operations
--------------------
  show         (READ)   — display current IP addresses and link state (ip addr).
  status       (READ)   — brief link-and-address summary (ip -brief addr).
  connections  (READ)   — list NetworkManager connection profiles (nmcli con show).
  interfaces   (READ)   — list network interfaces (ip link show).
  bring_up     (WRITE)  — bring an interface up (ip link set <if> up / nmcli con up).
  bring_down   (DESTRUCTIVE) — bring an interface down; may drop the active SSH
                               session: ip link set <if> down.
  set_ip       (WRITE)  — assign an IP address to an interface (nmcli con modify /
                           ip addr add <addr> dev <if>).

Permission mapping:
  READ       : show, status, connections, interfaces
  WRITE      : bring_up, set_ip
  DESTRUCTIVE: bring_down  (dropping the link you are on -> typed DESTROY)

Design rules
------------
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (REPL / router) MUST resolve the permission gate BEFORE calling
      execute(); this module does NOT call permissions.classify() internally.
  I4  The caller writes the audit record; this module never touches the audit log.
  I6  Zero tier/product/model names in this file.

Subprocess mocking
------------------
  On the dev host, nmcli and ip may or may not be present.
  Every test patches ``core.tools.network.run_subprocess`` so no real process
  is launched.  The tool builds a command vector and calls run_subprocess —
  it never inspects sys.platform.

Note on bring_down
------------------
  Bringing down the active network interface on a remote SSH host terminates
  the connection and is classified DESTRUCTIVE by the hardened classifier
  when synthesize_command emits ``ip link set <if> down``.  The classifier
  already recognises the ``ip ... set`` write shape; the ``down`` direction
  makes this a destructive lockout.  The OpSpec advisory here is DESTRUCTIVE;
  the real gate fires via permissions.classify in the REPL loop.
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

def _op_show(args: dict[str, Any]) -> ToolResult:
    """ip addr show — display all IP addresses and link state."""
    result = run_subprocess(["ip", "addr", "show"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Network addresses and interface state retrieved."
    else:
        summary = f"Address listing failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_status(args: dict[str, Any]) -> ToolResult:
    """ip -brief addr — brief one-line-per-interface summary."""
    result = run_subprocess(["ip", "-brief", "addr"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        summary = f"Network status: {len(lines)} interface(s) found."
    else:
        summary = f"Network status check failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_connections(args: dict[str, Any]) -> ToolResult:
    """nmcli con show — list NetworkManager connection profiles."""
    result = run_subprocess(["nmcli", "con", "show"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        # Count non-header lines
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        count = max(0, len(lines) - 1)  # subtract header row
        summary = f"Found {count} connection profile(s)."
    else:
        summary = f"Connection listing failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_interfaces(args: dict[str, Any]) -> ToolResult:
    """ip link show — list all network interfaces."""
    result = run_subprocess(["ip", "link", "show"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Network interfaces listed."
    else:
        summary = f"Interface listing failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_wifi(args: dict[str, Any]) -> ToolResult:
    """Report the wireless network (SSID) this host is connected to.

    ``ip addr`` shows addresses but never the SSID, so a dedicated path is
    required.  Primary source is NetworkManager:
        nmcli -t -f active,ssid dev wifi
    whose terse output is one ``active:ssid`` row per visible network; the row
    with ``active`` == ``yes`` is the connected one.  When NetworkManager is
    absent we fall back to ``iwgetid -r`` (the raw SSID of the active link).
    """
    result = run_subprocess(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    ssid = ""
    if result.ok and result.stdout.strip():
        for line in result.stdout.splitlines():
            # -t escapes the field separator inside values as "\:"; split on the
            # FIRST unescaped colon by temporarily masking the escaped ones.
            masked = line.replace("\\:", "\x00")
            parts = masked.split(":", 1)
            if len(parts) == 2 and parts[0].strip().lower() == "yes":
                ssid = parts[1].strip().replace("\x00", ":")
                break

    if not ssid:
        # Fall back to iwgetid when NetworkManager is not managing the link.
        fb = run_subprocess(["iwgetid", "-r"])
        if fb.ok and fb.stdout.strip():
            ssid = fb.stdout.strip()
            result = fb

    selinux = _maybe_selinux_hint(result.stderr)
    if ssid:
        return ToolResult(
            exit_code=0,
            stdout=ssid + "\n",
            stderr=result.stderr,
            summary=f"Connected wireless network: {ssid}." + selinux,
        )
    if result.ok:
        summary = "No active wireless connection found."
    else:
        summary = f"Wireless status check failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_bring_up(args: dict[str, Any]) -> ToolResult:
    """Bring a network interface up.

    Uses ``ip link set <iface> up`` (preferred) or a connection name via nmcli.
    Args accept either ``interface`` (device name, e.g. eth0) or
    ``connection`` (NM profile name).  At least one must be provided.
    """
    iface: str = args.get("interface", "")
    conn: str = args.get("connection", "")

    if iface:
        cmd = ["ip", "link", "set", iface, "up"]
        label = iface
    elif conn:
        cmd = ["nmcli", "con", "up", conn]
        label = conn
    else:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary="bring_up requires 'interface' or 'connection' argument.",
        )

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Interface '{label}' brought up."
    else:
        summary = f"Failed to bring up '{label}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_bring_down(args: dict[str, Any]) -> ToolResult:
    """Bring a network interface down — DESTRUCTIVE (may terminate SSH session).

    Emits ``ip link set <iface> down``.  The hardened classifier sees this
    command and escalates to DESTRUCTIVE when synthesize_command forwards it.
    The caller MUST have obtained typed confirmation before invoking execute().
    """
    iface: str = args["interface"]
    cmd = ["ip", "link", "set", iface, "down"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Interface '{iface}' brought down."
    else:
        summary = f"Failed to bring down '{iface}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_ip(args: dict[str, Any]) -> ToolResult:
    """Assign an IP address to an interface.

    Args:
      interface:  device name (e.g. eth0).
      address:    CIDR notation IP (e.g. 192.168.1.10/24).
      connection: (optional) NM connection profile name; if provided,
                  uses nmcli instead of ip addr add.
    """
    iface: str = args.get("interface", "")
    address: str = args["address"]
    conn: str = args.get("connection", "")

    if conn:
        # nmcli con modify <conn> ipv4.addresses <addr>
        cmd = ["nmcli", "con", "modify", conn, "ipv4.addresses", address]
        label = conn
    elif iface:
        cmd = ["ip", "addr", "add", address, "dev", iface]
        label = iface
    else:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary="set_ip requires 'interface' or 'connection' argument.",
        )

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Address '{address}' assigned to '{label}'."
    else:
        summary = f"Failed to set address on '{label}' (exit {result.exit_code})."
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
    "show":        _op_show,
    "status":      _op_status,
    "connections": _op_connections,
    "interfaces":  _op_interfaces,
    "wifi":        _op_wifi,
    "bring_up":    _op_bring_up,
    "bring_down":  _op_bring_down,
    "set_ip":      _op_set_ip,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a network operation and return a structured ToolResult.

    The caller (Phase 4 router / REPL) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log itself (I4 is the caller's responsibility).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for network tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_IFACE_ARG = ArgSpec(
    name="interface",
    type=str,
    required=False,
    description="Network interface device name (e.g. 'eth0', 'ens3').",
)

_CONN_ARG = ArgSpec(
    name="connection",
    type=str,
    required=False,
    description="NetworkManager connection profile name.",
)

_ADDRESS_ARG = ArgSpec(
    name="address",
    type=str,
    required=True,
    description="IP address in CIDR notation (e.g. '192.168.1.10/24').",
)

_IFACE_REQUIRED_ARG = ArgSpec(
    name="interface",
    type=str,
    required=True,
    description="Network interface device name (e.g. 'eth0', 'ens3').",
)

NETWORK_SPEC = ToolSpec(
    name="network",
    description="Inspect and configure network interfaces and connections.",
    ops={
        "show": OpSpec(
            op_name="show",
            permission_class=OpClass.READ,
            args=[],
            description="Show all IP addresses and interface state.",
        ),
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show a brief one-line-per-interface network summary.",
        ),
        "connections": OpSpec(
            op_name="connections",
            permission_class=OpClass.READ,
            args=[],
            description="List NetworkManager connection profiles.",
        ),
        "interfaces": OpSpec(
            op_name="interfaces",
            permission_class=OpClass.READ,
            args=[],
            description="List all network interfaces.",
        ),
        "wifi": OpSpec(
            op_name="wifi",
            permission_class=OpClass.READ,
            args=[],
            description="Show the wireless network (SSID) this host is connected to.",
        ),
        "bring_up": OpSpec(
            op_name="bring_up",
            permission_class=OpClass.WRITE,
            args=[_IFACE_ARG, _CONN_ARG],
            description="Bring a network interface or connection up.",
        ),
        "bring_down": OpSpec(
            op_name="bring_down",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_IFACE_REQUIRED_ARG],
            description="Bring a network interface down (may terminate the active session).",
        ),
        "set_ip": OpSpec(
            op_name="set_ip",
            permission_class=OpClass.WRITE,
            args=[_IFACE_ARG, _CONN_ARG, _ADDRESS_ARG],
            description="Assign an IP address to a network interface or connection.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(NETWORK_SPEC)
