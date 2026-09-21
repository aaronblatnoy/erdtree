"""finetune/simulate/network.py — Realistic Rocky Linux 9 output simulator
for the 'network' tool.

Public API
----------
simulate_network(op, args, ctx) -> dict
    Returns {exit_code, stdout, stderr, summary} for every real op of the
    network tool.  Outputs are realistic Rocky Linux 9 ip/nmcli command
    output.  Includes both success and realistic failure cases so generated
    traces teach error handling.

Design invariants
-----------------
INV-schema-sync   Op names and args are never hardcoded — the caller derives
                  them from the live registry.  This file only implements the
                  simulation logic for known ops; unknown ops raise ValueError.
INV-I2            Every `summary` string MUST pass assert_no_ai_language.
                  Summaries are tool output the assistant reasons over and may
                  echo back into assistant content.  Keep them plain.
INV-read-only-core  This file imports only from finetune.coreimports and the
                    standard library.  It never imports directly from core/.
INV-offline       No network I/O.  All outputs are statically constructed
                  from args and ctx.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from finetune.coreimports import assert_no_ai_language

# ---------------------------------------------------------------------------
# Context-extraction helpers
# ---------------------------------------------------------------------------

_DEFAULT_IFACE = "eth0"
_DEFAULT_SSID = "CorpWireless"


def _ctx_str(ctx: Any) -> str:
    """Safely coerce ctx to a string for substring scanning."""
    if ctx is None:
        return ""
    if isinstance(ctx, str):
        return ctx
    # Context objects may expose .snapshot_text or .to_prompt_text()
    if hasattr(ctx, "snapshot_text"):
        return str(ctx.snapshot_text)
    if hasattr(ctx, "to_prompt_text"):
        return str(ctx.to_prompt_text())
    return str(ctx)


def _pick_iface(args: dict, ctx: str) -> str:
    """Return the interface name from args, or a sensible default from ctx."""
    iface = args.get("interface", "")
    if iface:
        return iface
    # Try to find an interface name mentioned in ctx
    m = re.search(r"\b(en[ps]\d+s?\d*|eth\d+|ens\d+|enp\d+s\d+)\b", ctx)
    if m:
        return m.group(1)
    return _DEFAULT_IFACE


def _deterministic_variant(op: str, args: dict, ctx: str) -> bool:
    """Return True for the 'failure' variant of an op, deterministically.

    Uses a hash of (op, interface/connection/address) so that the same
    scenario always produces the same outcome while still exercising both
    success and failure branches across the corpus.

    Failure probability: ~1 in 4 calls (hash nibble == 0).
    """
    key = f"{op}:{args.get('interface','')}{args.get('connection','')}{args.get('address','')}"
    digest = hashlib.md5(key.encode()).hexdigest()  # noqa: S324 — not security-sensitive
    return digest[0] == "0"  # ~6% chance; adjust nibble count to tune


def _fail_variant(op: str, args: dict, ctx: str) -> bool:
    """1-in-4 deterministic failure variant using two nibbles."""
    key = f"{op}|{args.get('interface','')}{args.get('connection','')}{args.get('address','')}"
    digest = hashlib.md5(key.encode()).hexdigest()  # noqa: S324
    return int(digest[:2], 16) < 64  # ~25 % failure rate


# ---------------------------------------------------------------------------
# Realistic interface data templates
# ---------------------------------------------------------------------------

_SHOW_OUTPUT = """\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 52:54:00:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.42/24 brd 192.168.1.255 scope global dynamic eth0
       valid_lft 85234sec preferred_lft 85234sec
    inet6 fe80::5054:ff:feab:cdef/64 scope link
       valid_lft forever preferred_lft forever
3: eth1: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN group default qlen 1000
    link/ether 52:54:00:11:22:33 brd ff:ff:ff:ff:ff:ff
"""

_STATUS_OUTPUT = """\
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.1.42/24 fe80::5054:ff:feab:cdef/64
eth1             DOWN
"""

_CONNECTIONS_OUTPUT = """\
NAME              UUID                                  TYPE      DEVICE
System eth0       a1b2c3d4-e5f6-7890-abcd-ef1234567890  ethernet  eth0
Wired connection 1  b2c3d4e5-f6a7-8901-bcde-f12345678901  ethernet  --
CorpWireless      c3d4e5f6-a7b8-9012-cdef-012345678902  wifi      --
"""

_INTERFACES_OUTPUT = """\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000
    link/ether 52:54:00:ab:cd:ef brd ff:ff:ff:ff:ff:ff
3: eth1: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ether 52:54:00:11:22:33 brd ff:ff:ff:ff:ff:ff
"""

_WIFI_NM_OUTPUT = """\
yes:CorpWireless
no:GuestNetwork
no:Neighbor-5G
"""

# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------


def _sim_show(args: dict, ctx: str) -> dict:
    """ip addr show output."""
    fail = _fail_variant("show", args, ctx)
    if fail:
        stderr = "Cannot open network namespace: No such file or directory"
        summary = "Address listing failed: network namespace unavailable."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": stderr, "summary": summary}

    # Optionally customise the IP based on ctx
    m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+)", ctx)
    ip_line = m.group(1) if m else "192.168.1.42/24"
    output = _SHOW_OUTPUT.replace("192.168.1.42/24", ip_line)

    summary = "Network addresses and interface state retrieved."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": output, "stderr": "", "summary": summary}


def _sim_status(args: dict, ctx: str) -> dict:
    """ip -brief addr output."""
    fail = _fail_variant("status", args, ctx)
    if fail:
        stderr = "ip: command not found"
        summary = "Network status check failed: ip utility not found on PATH."
        assert_no_ai_language(summary)
        return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}

    summary = "Network status: 2 interface(s) found (eth0 UP, eth1 DOWN)."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": _STATUS_OUTPUT, "stderr": "", "summary": summary}


def _sim_connections(args: dict, ctx: str) -> dict:
    """nmcli con show output."""
    fail = _fail_variant("connections", args, ctx)
    if fail:
        stderr = (
            "Error: NetworkManager is not running.\n"
            "  (try: systemctl start NetworkManager)"
        )
        summary = "Connection listing failed: NetworkManager is not running."
        assert_no_ai_language(summary)
        return {"exit_code": 10, "stdout": "", "stderr": stderr, "summary": summary}

    # Check ctx for a connection profile name to include
    conn_name = "System eth0"
    m = re.search(r"connection[:\s]+([A-Za-z0-9_\-]+)", ctx, re.IGNORECASE)
    if m:
        conn_name = m.group(1)

    output = _CONNECTIONS_OUTPUT.replace("System eth0", conn_name, 1)
    summary = "Found 3 connection profile(s)."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": output, "stderr": "", "summary": summary}


def _sim_interfaces(args: dict, ctx: str) -> dict:
    """ip link show output."""
    fail = _fail_variant("interfaces", args, ctx)
    if fail:
        stderr = "RTNETLINK answers: Operation not permitted"
        summary = "Interface listing failed: operation not permitted (check capabilities)."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": stderr, "summary": summary}

    summary = "Network interfaces listed: lo, eth0 (UP), eth1 (DOWN)."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": _INTERFACES_OUTPUT, "stderr": "", "summary": summary}


def _sim_listening(args: dict, ctx: str) -> dict:
    """ss -tulpn output."""
    if _fail_variant("listening", args, ctx):
        summary = "Listening-socket query failed (exit 127)."
        assert_no_ai_language(summary)
        return {"exit_code": 127, "stdout": "", "stderr": "ss: command not found", "summary": summary}
    out = ("Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
           "tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*     users:((\"sshd\",pid=1042,fd=3))\n"
           "tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*     users:((\"nginx\",pid=1377,fd=6))\n"
           "tcp   LISTEN 0      244        127.0.0.1:5432      0.0.0.0:*     users:((\"postgres\",pid=1511,fd=5))\n")
    summary = "3 listening socket(s), with the owning process where visible."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": out, "stderr": "", "summary": summary}


def _sim_current(args: dict, ctx: str) -> dict:
    """Default route, interface, DNS."""
    if _fail_variant("current", args, ctx):
        summary = "No default route: this machine is not connected to a network."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": "", "summary": summary}
    out = ("default route: via 10.0.0.1 on eth0\n"
           "interface:     eth0 UP 10.0.0.15/24\n"
           "dns servers:   10.0.0.2, 10.0.0.3\n")
    summary = "Connected through eth0, gateway 10.0.0.1."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": out, "stderr": "", "summary": summary}


def _sim_wifi(args: dict, ctx: str) -> dict:
    """nmcli wifi SSID query output."""
    fail = _fail_variant("wifi", args, ctx)
    if fail:
        # Simulate a wired-only host with no wireless device
        stderr = "Error: No Wi-Fi device found."
        summary = "Wireless status check failed: no wireless device present on this host."
        assert_no_ai_language(summary)
        return {"exit_code": 10, "stdout": "", "stderr": stderr, "summary": summary}

    # Check ctx for an SSID mention
    m = re.search(r"ssid[:\s]+([A-Za-z0-9_\-]+)", ctx, re.IGNORECASE)
    ssid = m.group(1) if m else _DEFAULT_SSID

    # Produce nmcli terse output
    output = f"yes:{ssid}\nno:GuestNetwork\n"
    summary = f"Connected wireless network: {ssid}."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": ssid + "\n", "stderr": "", "summary": summary}


def _sim_bring_up(args: dict, ctx: str) -> dict:
    """ip link set <iface> up / nmcli con up."""
    iface = args.get("interface", "")
    conn = args.get("connection", "")
    label = iface or conn or _pick_iface(args, ctx)

    fail = _fail_variant("bring_up", args, ctx)
    if fail:
        if not iface and not conn:
            stderr = ""
            summary = "bring_up requires 'interface' or 'connection' argument."
            assert_no_ai_language(summary)
            return {"exit_code": 1, "stdout": "", "stderr": stderr, "summary": summary}
        stderr = f"RTNETLINK answers: No such device ('{label}' not found)"
        summary = f"Failed to bring up '{label}': interface not found."
        assert_no_ai_language(summary)
        return {"exit_code": 2, "stdout": "", "stderr": stderr, "summary": summary}

    if not iface and not conn:
        summary = "bring_up requires 'interface' or 'connection' argument."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": "", "summary": summary}

    if conn:
        stdout = f"Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/4)\n"
    else:
        stdout = ""  # ip link set returns no stdout on success

    summary = f"Interface '{label}' brought up."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": stdout, "stderr": "", "summary": summary}


def _sim_bring_down(args: dict, ctx: str) -> dict:
    """ip link set <iface> down — DESTRUCTIVE."""
    iface = args.get("interface", "") or _pick_iface(args, ctx)

    fail = _fail_variant("bring_down", args, ctx)
    if fail:
        stderr = f"RTNETLINK answers: No such device ('{iface}' not found)"
        summary = f"Failed to bring down '{iface}': interface not found."
        assert_no_ai_language(summary)
        return {"exit_code": 2, "stdout": "", "stderr": stderr, "summary": summary}

    # Simulate the connection drop that follows taking down the active link
    summary = f"Interface '{iface}' brought down."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": "", "stderr": "", "summary": summary}


def _sim_set_ip(args: dict, ctx: str) -> dict:
    """ip addr add / nmcli con modify ipv4.addresses."""
    iface = args.get("interface", "")
    conn = args.get("connection", "")
    address = args.get("address", "")
    label = iface or conn or _pick_iface(args, ctx)

    # Validate address presence
    if not address:
        summary = "set_ip requires an 'address' argument in CIDR notation."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": "", "summary": summary}

    if not iface and not conn:
        summary = "set_ip requires 'interface' or 'connection' argument."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": "", "summary": summary}

    fail = _fail_variant("set_ip", args, ctx)
    if fail:
        # Simulate RTNETLINK permission or invalid address errors
        stderr = f"Error: Address {address!r} does not look like a valid CIDR address."
        summary = f"Failed to set address on '{label}': invalid CIDR address '{address}'."
        assert_no_ai_language(summary)
        return {"exit_code": 1, "stdout": "", "stderr": stderr, "summary": summary}

    if conn:
        stdout = (
            f"Connection '{conn}' (b2c3d4e5-f6a7-8901-bcde-f12345678901) "
            f"successfully updated.\n"
        )
    else:
        stdout = ""  # ip addr add returns no stdout on success

    summary = f"Address '{address}' assigned to '{label}'."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": stdout, "stderr": "", "summary": summary}


# ---------------------------------------------------------------------------
# Dispatch table — maps op name -> simulator function
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "show":        _sim_show,
    "status":      _sim_status,
    "connections": _sim_connections,
    "interfaces":  _sim_interfaces,
    "listening":   _sim_listening,
    "current":     _sim_current,
    "wifi":        _sim_wifi,
    "bring_up":    _sim_bring_up,
    "bring_down":  _sim_bring_down,
    "set_ip":      _sim_set_ip,
}

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def simulate_network(op: str, args: dict, ctx: Any) -> dict:
    """Simulate a 'network' tool operation.

    Parameters
    ----------
    op:   Operation name (must be a real op declared in NETWORK_SPEC).
    args: Argument dict (mirrors what the router passes to network.execute()).
    ctx:  System snapshot string or object (used to key outputs on the host
          environment: interface names, IPs, SSIDs found in the context text).

    Returns
    -------
    dict with exactly four keys: exit_code (int), stdout (str), stderr (str),
    summary (str).  The summary is always I2-clean.

    Raises
    ------
    ValueError if `op` is not a recognised network operation.
    """
    if args is None:
        args = {}
    ctx_text = _ctx_str(ctx)

    handler = _DISPATCH.get(op)
    if handler is None:
        raise ValueError(
            f"simulate_network: unknown op '{op}'. "
            f"Known ops: {sorted(_DISPATCH)}"
        )

    result = handler(args, ctx_text)

    # Structural invariant: all four keys must be present and summary I2-clean.
    assert set(result) == {"exit_code", "stdout", "stderr", "summary"}, (
        f"simulate_network({op!r}) returned wrong keys: {set(result)}"
    )
    assert_no_ai_language(result["summary"])

    return result


# Convenience alias so the P3 join's dispatch table can call a uniform name.
__all__ = ["simulate_network"]
