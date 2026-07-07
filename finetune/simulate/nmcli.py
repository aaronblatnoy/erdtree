"""finetune/simulate/nmcli.py — Rocky Linux 9 output simulator for the 'nmcli' tool.

Public API
----------
simulate_nmcli(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 10 real operations declared in core/tools/nmcli.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real nmcli behaviour:
    0  — success
    4  — connection profile / device not found (general NM error)
    10 — timeout connecting to NetworkManager daemon
* stdout/stderr reflect actual Rocky 9 nmcli output format.
* Failure triggers are deterministic via hash-based scatter and keyword tokens:
  a profile name containing "notfound"/"noexist"/"missing"/"bogus"/"fail"
  triggers a failure branch; a ~15% hash scatter adds variety.
* ctx is used to determine whether a connection profile is currently active:
  if ctx is a dict, ctx.get("active_connections", []) is consulted;
  if ctx is a str, the profile name is searched in the snapshot text.

I2 compliance
-------------
All summary strings are I2-clean: no AI, LLM, model, agent, agentic, ollama,
inference, neural, or language model terms.

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


def _profile_active(name: str, ctx: Any) -> bool:
    """Return True if the connection profile appears active in ctx."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_connections", [])
        return name in active or any(name in a for a in active)
    if isinstance(ctx, str):
        return name in ctx
    return False


def _profile_not_found(name: str) -> bool:
    """Deterministically decide whether a profile name should trigger not-found."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "missing", "bogus", "fail", "broken"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
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


def _nm_not_running() -> bool:
    """~5% chance NM daemon is unavailable (deterministic via fixed seed)."""
    return False  # kept stable for corpus consistency; override in specific branches


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_device_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    active = _profile_active("eth0", ctx) or True  # devices always listed
    stdout = (
        "DEVICE  TYPE      STATE      CONNECTION\n"
        "eth0    ethernet  connected  Wired connection 1\n"
        "lo      loopback  unmanaged  --\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="NetworkManager device status retrieved.",
    )


def _sim_connection_show(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")
    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Connection profile '{name}' not found or could not be shown (exit 4).",
        )
    active_str = "activated" if _profile_active(name, ctx) else "deactivated"
    stdout = (
        f"connection.id:                          {name}\n"
        f"connection.uuid:                        aabbccdd-1122-3344-5566-778899001122\n"
        f"connection.stable-id:                   --\n"
        f"connection.type:                        802-3-ethernet\n"
        f"connection.interface-name:              eth0\n"
        f"connection.autoconnect:                 yes\n"
        f"ipv4.method:                            auto\n"
        f"ipv4.dns:                               8.8.8.8\n"
        f"ipv4.addresses:                         192.168.1.10/24\n"
        f"ipv4.gateway:                           192.168.1.1\n"
        f"GENERAL.STATE:                          {active_str}\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Connection profile '{name}' details retrieved.",
    )


def _sim_connection_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    con_type = args.get("type", "ethernet")
    con_name = args.get("con_name", "new-connection")
    ifname = args.get("ifname", "eth0")

    if _profile_not_found(con_name):
        stderr = (
            f"Error: Failed to add '{con_name}': invalid profile type or interface.\n"
        )
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create connection profile '{con_name}' (exit 4).",
        )

    uuid = "deadbeef-0001-0002-0003-" + hashlib.md5(con_name.encode()).hexdigest()[:12]
    stdout = (
        f"Connection '{con_name}' ({uuid}) successfully added.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Connection profile '{con_name}' of type '{con_type}' "
            f"created on interface '{ifname}'."
        ),
    )


def _sim_connection_modify(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")
    prop = args.get("property", "ipv4.addresses")
    value = args.get("value", "")

    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to modify connection profile '{name}' (exit 4).",
        )

    # nmcli modify exits 0 with empty stdout on success
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Connection profile '{name}': property '{prop}' set to '{value}'.",
    )


def _sim_connection_up(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")

    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to activate connection profile '{name}' (exit 4).",
        )

    # Hash-based occasional failure (carrier not found, etc.)
    h = int(hashlib.md5((name + "up").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = f"Error: Connection activation failed: No carrier on interface eth0.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to activate connection profile '{name}' (exit 4).",
        )

    uuid = "deadbeef-0001-0002-0003-" + hashlib.md5(name.encode()).hexdigest()[:12]
    stdout = (
        f"Connection successfully activated (D-Bus active path: "
        f"/org/freedesktop/NetworkManager/ActiveConnection/3)\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Connection profile '{name}' activated.",
    )


def _sim_connection_down(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")

    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to deactivate connection profile '{name}' (exit 4).",
        )

    if not _profile_active(name, ctx):
        # Already down — nmcli returns error 4
        stderr = f"Error: {name} - connection profile is not currently active.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Connection profile '{name}' was not active; no change made.",
        )

    stdout = f"Connection '{name}' successfully deactivated.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Connection profile '{name}' deactivated.",
    )


def _sim_connection_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")

    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to delete connection profile '{name}' (exit 4).",
        )

    uuid = "deadbeef-0001-0002-0003-" + hashlib.md5(name.encode()).hexdigest()[:12]
    stdout = f"Connection '{name}' ({uuid}) successfully deleted.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Connection profile '{name}' deleted.",
    )


def _sim_wifi_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    ifname = args.get("ifname", "")
    # Realistic nmcli device wifi list output
    stdout = (
        "IN-USE  BSSID              SSID              MODE   CHAN  RATE        SIGNAL  BARS  SECURITY\n"
        "        AA:BB:CC:DD:EE:01  HomeNetwork       Infra  6     130 Mbit/s  85      ▂▄▆█  WPA2\n"
        "*       11:22:33:44:55:66  OfficeWifi        Infra  11    195 Mbit/s  72      ▂▄▆_  WPA2\n"
        "        CC:DD:EE:FF:00:11  GuestNetwork      Infra  1     54 Mbit/s   40      ▂▄__  WPA2\n"
        "        FF:EE:DD:CC:BB:AA  OpenHotspot       Infra  36    130 Mbit/s  30      ▂___  --\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Available Wi-Fi networks retrieved.",
    )


def _sim_wifi_connect(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    ssid = args.get("ssid", "unknown-ssid")

    if _profile_not_found(ssid):
        stderr = f"Error: No Wi-Fi network with SSID '{ssid}' found.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to connect to Wi-Fi network '{ssid}' (exit 4).",
        )

    # Hash-based occasional auth failure
    h = int(hashlib.md5((ssid + "wifi").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"Error: Connection activation failed: Secrets were required, "
            f"but not provided.\n"
        )
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to connect to Wi-Fi network '{ssid}' (exit 4).",
        )

    stdout = f"Device 'wlan0' successfully activated with 'deadbeef-0001-0002-0003-aabbccddeeff'.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Connected to Wi-Fi network '{ssid}'.",
    )


def _sim_dns_configure(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "unknown-profile")
    dns = args.get("dns", "8.8.8.8")

    if _profile_not_found(name):
        stderr = f"Error: {name} - no such connection profile.\n"
        return _make_result(
            exit_code=4,
            stdout="",
            stderr=stderr,
            summary=f"Failed to configure DNS on connection profile '{name}' (exit 4).",
        )

    # nmcli modify ipv4.dns exits 0 with empty stdout
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"DNS servers for connection profile '{name}' set to '{dns}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "device_status":    _sim_device_status,
    "connection_show":  _sim_connection_show,
    "connection_add":   _sim_connection_add,
    "connection_modify": _sim_connection_modify,
    "connection_up":    _sim_connection_up,
    "connection_down":  _sim_connection_down,
    "connection_delete": _sim_connection_delete,
    "wifi_list":        _sim_wifi_list,
    "wifi_connect":     _sim_wifi_connect,
    "dns_configure":    _sim_dns_configure,
}


def simulate_nmcli(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'nmcli' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 10 real ops declared in
           core/tools/nmcli.py.
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_connections' list.

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
            f"simulate_nmcli: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
