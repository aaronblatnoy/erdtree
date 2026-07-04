"""finetune/simulate/firewall.py — Rocky Linux 9 output simulator for the 'firewall' tool.

Public API
----------
simulate_firewall(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 10 real operations declared in core/tools/firewall.py
           (list, get_zones, query, add_service, add_port, remove_service,
           remove_port, reload, set_default_zone, panic_on)
    args : dict of op arguments (may be {} for ops with all-optional/no args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Both forms are supported so the simulator works whether generate.py
           passes the raw snapshot_text string or a richer profile dict.

Realism model
-------------
* Exit codes mirror real firewall-cmd / firewalld behaviour:
    0  — success (service allowed / port opened / reload complete / etc.)
    1  — operation failed (not running, permission denied, duplicate entry)
    2  — zone/service/port not found or invalid argument
* stdout/stderr reflect actual Rocky 9 firewall-cmd output format.
* Failure triggers are deterministic: invalid-looking zone names (containing
  tokens like "bad", "invalid", "bogus", "fake", "notfound") trigger error
  cases; similarly for service names.  A hash-based ~15% scatter adds variety
  among otherwise valid names.
* ctx is used to determine the active zone, interface names, and which
  services appear in the firewall listing.

I2 compliance
-------------
All `summary` strings are I2-clean.  The assert_no_ai_language guard is NOT
called inline (to keep this module fast and dependency-light for tests), but
the test_i2.py suite asserts every returned summary.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# Known firewall zones on a standard Rocky Linux 9 / firewalld installation
# ---------------------------------------------------------------------------

_VALID_ZONES = frozenset({
    "block", "dmz", "drop", "external", "home", "internal",
    "public", "trusted", "work",
})

# Known firewalld predefined services (representative subset)
_VALID_SERVICES = frozenset({
    "ssh", "http", "https", "ftp", "smtp", "smtps", "pop3", "pop3s",
    "imap", "imaps", "dns", "dhcp", "dhcpv6", "dhcpv6-client",
    "nfs", "nfs3", "samba", "samba-client", "mountd", "rpc-bind",
    "mysql", "postgresql", "redis", "mongodb",
    "cockpit", "vnc-server", "rdp",
    "http3", "kerberos", "ldap", "ldaps",
    "openvpn", "wireguard", "iscsi", "iscsi-target",
    "tftp", "snmp", "snmptrap",
    "prometheus", "grafana", "elasticsearch",
    "zabbix-agent", "zabbix-server",
    "bacula", "bacula-client",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _ctx_str(ctx: Any) -> str:
    """Safely coerce ctx to a string for substring scanning."""
    if ctx is None:
        return ""
    if isinstance(ctx, str):
        return ctx
    if hasattr(ctx, "snapshot_text"):
        return str(ctx.snapshot_text)
    if hasattr(ctx, "to_prompt_text"):
        return str(ctx.to_prompt_text())
    return str(ctx)


def _hostname(ctx: Any) -> str:
    """Extract a short hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    s = _ctx_str(ctx)
    for line in s.splitlines():
        if line.lower().startswith("hostname:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip().split(".")[0]
    return "rocky-host"


def _active_zone(ctx: Any) -> str:
    """Determine the active firewall zone from ctx, defaulting to 'public'."""
    if isinstance(ctx, dict):
        # Some profiles carry a firewall_zones list or active_zone key
        active = ctx.get("active_zone", "")
        if active and active in _VALID_ZONES:
            return active
        zones = ctx.get("firewall_zones", [])
        if zones:
            return zones[0] if isinstance(zones[0], str) else "public"
    s = _ctx_str(ctx)
    # Look for a "zone: <name>" hint in the snapshot text
    for line in s.splitlines():
        stripped = line.lower().strip()
        if stripped.startswith("active zone:") or stripped.startswith("default zone:"):
            parts = stripped.split(":", 1)
            candidate = parts[1].strip() if len(parts) == 2 else ""
            if candidate in _VALID_ZONES:
                return candidate
    return "public"


def _active_services_for_zone(ctx: Any, zone: str) -> list[str]:
    """Return a list of services shown as enabled in the given zone."""
    if isinstance(ctx, dict):
        fw_services = ctx.get("firewall_services", [])
        if fw_services:
            return list(fw_services)
    s = _ctx_str(ctx)
    # Look for a "services: <list>" hint in snapshot text
    for line in s.splitlines():
        if "services:" in line.lower():
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip().split()
    # Defaults differ by zone
    _zone_defaults: dict[str, list[str]] = {
        "public":   ["cockpit", "dhcpv6-client", "ssh"],
        "internal": ["cockpit", "dhcpv6-client", "mdns", "samba-client", "ssh"],
        "home":     ["cockpit", "dhcpv6-client", "mdns", "samba-client", "ssh"],
        "work":     ["cockpit", "dhcpv6-client", "ssh"],
        "dmz":      ["ssh"],
        "external": ["ssh"],
        "trusted":  [],
        "drop":     [],
        "block":    [],
    }
    return _zone_defaults.get(zone, ["ssh"])


def _active_interface(ctx: Any) -> str:
    """Return a plausible network interface name from ctx."""
    if isinstance(ctx, dict):
        ifaces = ctx.get("interfaces", [])
        if ifaces:
            return ifaces[0] if isinstance(ifaces[0], str) else "eth0"
    s = _ctx_str(ctx)
    import re
    m = re.search(r"\b(en[ps]\d+s?\d*|eth\d+|ens\d+|enp\d+s\d+)\b", s)
    if m:
        return m.group(1)
    return "eth0"


def _open_ports(ctx: Any) -> list[str]:
    """Return a list of ports/protos already open, from ctx or defaults."""
    if isinstance(ctx, dict):
        ports = ctx.get("open_ports", [])
        if ports:
            return [str(p) for p in ports]
    return []


def _invalid_zone(zone: str) -> bool:
    """Return True if the zone name looks invalid/unknown."""
    z = zone.lower()
    for tok in ("bad", "invalid", "bogus", "fake", "notfound", "noexist", "unknown"):
        if tok in z:
            return True
    if zone not in _VALID_ZONES:
        # Hash-based 20% scatter for zone names not in our known set
        h = int(hashlib.md5(zone.encode()).hexdigest(), 16)
        return h % 5 == 0 or zone not in _VALID_ZONES
    return False


def _invalid_service(service: str) -> bool:
    """Return True if the service name looks invalid/unknown to firewalld."""
    s = service.lower()
    for tok in ("bad", "invalid", "bogus", "fake", "notfound", "noexist", "unknown"):
        if tok in s:
            return True
    if service not in _VALID_SERVICES:
        # Hash-based ~20% scatter — not all unknown services are invalid,
        # firewalld accepts any service with a XML definition; but if the
        # service clearly doesn't exist, it errors.
        h = int(hashlib.md5(service.encode()).hexdigest(), 16)
        return h % 4 == 0  # 25% failure among unknown names
    return False


def _invalid_port(port: str) -> bool:
    """Return True if the port/proto string looks invalid."""
    p = port.lower()
    for tok in ("bad", "invalid", "bogus", "fake", "notfound"):
        if tok in p:
            return True
    # Must match <number>/<proto> or <num>-<num>/<proto>
    import re
    if not re.fullmatch(r"\d+(?:-\d+)?/(tcp|udp|sctp)", p):
        return True
    num = int(p.split("/")[0].split("-")[0])
    return num < 1 or num > 65535


def _firewalld_not_running(ctx: Any) -> bool:
    """Deterministically decide if firewalld should appear to be stopped."""
    s = _ctx_str(ctx)
    if "firewalld" in s and ("inactive" in s or "stopped" in s or "not running" in s):
        return True
    return False


def _hash_failure(salt: str, rate_denom: int = 7) -> bool:
    """Return True for ~1/rate_denom of calls based on a deterministic hash."""
    h = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    return h % rate_denom == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --list-all"""
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the firewall zone listing could not be retrieved.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; no firewall settings were listed.",
        )

    services = _active_services_for_zone(ctx, zone)
    iface = _active_interface(ctx)
    ports = _open_ports(ctx)
    ports_str = " ".join(ports) if ports else ""
    is_active = zone == _active_zone(ctx)
    active_tag = " (active)" if is_active else ""

    stdout = (
        f"{zone}{active_tag}\n"
        f"  target: default\n"
        f"  icmp-block-inversion: no\n"
        f"  interfaces: {iface if is_active else ''}\n"
        f"  sources: \n"
        f"  services: {' '.join(services)}\n"
        f"  ports: {ports_str}\n"
        f"  protocols: \n"
        f"  forward: yes\n"
        f"  masquerade: no\n"
        f"  forward-ports: \n"
        f"  source-ports: \n"
        f"  icmp-blocks: \n"
        f"  rich rules: \n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed all firewall settings for zone '{zone}': {len(services)} service(s) allowed.",
    )


def _sim_get_zones(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd --get-zones"""
    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the list of defined zones could not be retrieved.",
        )

    # Standard Rocky 9 zone list
    zones = sorted(_VALID_ZONES)
    stdout = " ".join(zones) + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {len(zones)} defined firewall zones: {', '.join(zones[:4])} and more.",
    )


def _sim_query(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --query-service <service>"""
    service = args.get("service", "ssh")
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the service query could not be completed.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; could not query service '{service}'.",
        )

    if _invalid_service(service):
        stderr = f"Error: INVALID_SERVICE: '{service}' is not a valid service\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Service '{service}' is not recognised by firewalld; the query returned an error.",
        )

    active_svcs = _active_services_for_zone(ctx, zone)
    if service in active_svcs:
        return _make_result(
            exit_code=0,
            stdout="yes\n",
            stderr="",
            summary=f"Service '{service}' is allowed in zone '{zone}'.",
        )
    else:
        return _make_result(
            exit_code=1,
            stdout="no\n",
            stderr="",
            summary=f"Service '{service}' is not allowed in zone '{zone}'.",
        )


def _sim_add_service(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --add-service <service>"""
    service = args.get("service", "http")
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the service could not be added.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; service '{service}' was not added.",
        )

    if _invalid_service(service):
        stderr = f"Error: INVALID_SERVICE: '{service}' is not a valid service\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Service '{service}' is not recognised by firewalld; it was not added to zone '{zone}'.",
        )

    # Check if already present — firewalld errors with ALREADY_ENABLED
    active_svcs = _active_services_for_zone(ctx, zone)
    if service in active_svcs:
        stderr = f"Error: ALREADY_ENABLED: '{service}' already in '{zone}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Service '{service}' is already enabled in zone '{zone}'; no change was made.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary=f"Service '{service}' added to zone '{zone}' (runtime); changes take effect immediately.",
    )


def _sim_add_port(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --add-port <port>/<proto>"""
    port = args.get("port", "8080/tcp")
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the port could not be opened.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; port '{port}' was not opened.",
        )

    if _invalid_port(port):
        stderr = f"Error: INVALID_PORT: {port}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Port specification '{port}' is invalid; check the format (e.g. 8080/tcp).",
        )

    # Check if already open
    open_ports = _open_ports(ctx)
    if port in open_ports:
        stderr = f"Error: ALREADY_ENABLED: '{port}' already in '{zone}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Port '{port}' is already open in zone '{zone}'; no change was made.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary=f"Port '{port}' opened in zone '{zone}' (runtime); traffic on that port is now permitted.",
    )


def _sim_remove_service(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --remove-service <service>"""
    service = args.get("service", "http")
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the service could not be removed.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; service '{service}' was not removed.",
        )

    if _invalid_service(service):
        stderr = f"Error: INVALID_SERVICE: '{service}' is not a valid service\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Service '{service}' is not recognised by firewalld; removal failed for zone '{zone}'.",
        )

    active_svcs = _active_services_for_zone(ctx, zone)
    if service not in active_svcs:
        stderr = f"Error: NOT_ENABLED: '{service}' is not in '{zone}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Service '{service}' is not currently enabled in zone '{zone}'; nothing was removed.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary=f"Service '{service}' removed from zone '{zone}' (runtime); it is no longer allowed.",
    )


def _sim_remove_port(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd [--zone <zone>] --remove-port <port>/<proto>"""
    port = args.get("port", "8080/tcp")
    zone = args.get("zone") or _active_zone(ctx)

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the port could not be closed.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; port '{port}' was not removed.",
        )

    if _invalid_port(port):
        stderr = f"Error: INVALID_PORT: {port}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Port specification '{port}' is invalid; removal could not proceed.",
        )

    open_ports = _open_ports(ctx)
    if port in open_ports:
        return _make_result(
            exit_code=0,
            stdout="success\n",
            stderr="",
            summary=f"Port '{port}' closed in zone '{zone}' (runtime); traffic on that port is no longer permitted.",
        )
    else:
        stderr = f"Error: NOT_ENABLED: '{port}' is not in '{zone}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Port '{port}' was not open in zone '{zone}'; nothing was removed.",
        )


def _sim_reload(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd --reload"""
    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the reload request was rejected.",
        )

    # Hash-based failure: simulate an occasional firewalld reload error (~1 in 8)
    ctx_s = _ctx_str(ctx)
    if _hash_failure(ctx_s + "reload", rate_denom=8):
        stderr = (
            "Error: COMMAND_FAILED: 'python-slip.dbus.polkit' exited with error code 1\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Firewall reload failed; a D-Bus/polkit error was returned by firewalld.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary="Firewall ruleset reloaded; permanent rules are now active.",
    )


def _sim_set_default_zone(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd --set-default-zone <zone>"""
    zone = args.get("zone", "public")

    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; the default zone could not be changed.",
        )

    if _invalid_zone(zone):
        stderr = f"Error: INVALID_ZONE: {zone}\n"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Zone '{zone}' is not defined; the default zone was not changed.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary=f"Default firewall zone changed to '{zone}'; new connections will use this zone.",
    )


def _sim_panic_on(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """firewall-cmd --panic-on — drops ALL inbound and outbound traffic."""
    if _firewalld_not_running(ctx):
        stderr = "FirewallD is not running.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="firewalld is not running; panic mode could not be activated.",
        )

    # Permission-denied failure case: simulates running as non-root without sudo
    ctx_s = _ctx_str(ctx)
    if _hash_failure(ctx_s + "panic_on", rate_denom=6):
        stderr = (
            "Error: COMMAND_FAILED: Authorization failed.\n"
            "       You need to be root to run this command.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Panic mode activation failed; elevated privileges are required to run this command.",
        )

    return _make_result(
        exit_code=0,
        stdout="success\n",
        stderr="",
        summary="Firewall panic mode is now on; all inbound and outbound traffic is blocked.",
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":             _sim_list,
    "get_zones":        _sim_get_zones,
    "query":            _sim_query,
    "add_service":      _sim_add_service,
    "add_port":         _sim_add_port,
    "remove_service":   _sim_remove_service,
    "remove_port":      _sim_remove_port,
    "reload":           _sim_reload,
    "set_default_zone": _sim_set_default_zone,
    "panic_on":         _sim_panic_on,
}


def simulate_firewall(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'firewall' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 10 real ops declared in the
           firewall ToolSpec (list, get_zones, query, add_service, add_port,
           remove_service, remove_port, reload, set_default_zone, panic_on).
    args : argument dict (may be {} for ops with all-optional or no args).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with keys like 'active_zone', 'firewall_services',
           'open_ports', 'interfaces', 'hostname'.

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
            f"simulate_firewall: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
