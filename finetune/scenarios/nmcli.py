"""finetune/scenarios/nmcli.py — Scenario corpus for the 'nmcli' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  device_status    READ        — show NM device and connection overview
  connection_show  READ        — show details of a named connection profile
  connection_add   WRITE       — create a new connection profile
  connection_modify WRITE      — modify a property of an existing profile
  connection_up    WRITE       — activate a connection profile
  connection_down  WRITE       — deactivate a connection profile
  connection_delete DESTRUCTIVE — permanently delete a connection profile
  wifi_list        READ        — list visible Wi-Fi access points
  wifi_connect     WRITE       — connect to a Wi-Fi network by SSID
  dns_configure    WRITE       — set DNS servers on a connection profile

Coverage targets
----------------
  >= 40 entries total across all 10 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the explicit-confirm gate for connection_delete.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass
# Compatible field names are EXACT so the Phase-13 JOIN can unify without renames.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------


def _pc(op: str) -> OpClass:
    """Return the live permission class for an nmcli operation."""
    return registry.get("nmcli").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # device_status  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-device_status-0001",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("device_status"),
        complexity="single",
        user_input="show me the status of all network devices managed by NetworkManager",
        notes="Simple READ: list all NM devices and their connection state.",
    ),
    Scenario(
        id="nmcli-device_status-0002",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("device_status"),
        complexity="single",
        user_input="what is the current state of my network interfaces?",
        notes="NM device overview — quick connectivity check.",
    ),
    Scenario(
        id="nmcli-device_status-0003",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("device_status"),
        complexity="diagnostic",
        user_input="eth0 is not coming up — show me which devices NetworkManager sees",
        notes="Diagnostic: verify NM device visibility before investigating connection profiles.",
    ),
    Scenario(
        id="nmcli-device_status-0004",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("device_status"),
        complexity="multi",
        user_input="check device status and then show me the active connection profiles",
        notes="Multi-step: device overview then profile inspection.",
    ),
    Scenario(
        id="nmcli-device_status-0005",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("device_status"),
        complexity="single",
        user_input="list all network devices and show whether they are connected",
        notes="READ: NM device state inventory for an audit.",
    ),

    # =========================================================================
    # connection_show  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_show-0001",
        tool="nmcli",
        operation="connection_show",
        permission_class=_pc("connection_show"),
        complexity="single",
        user_input="show me the details of the 'Wired connection 1' profile",
        notes="READ: inspect a specific NM profile's full settings.",
    ),
    Scenario(
        id="nmcli-connection_show-0002",
        tool="nmcli",
        operation="connection_show",
        permission_class=_pc("connection_show"),
        complexity="single",
        user_input="display the configuration of the 'ens192-static' connection",
        notes="READ: check IP, DNS, and gateway settings on a static profile.",
    ),
    Scenario(
        id="nmcli-connection_show-0003",
        tool="nmcli",
        operation="connection_show",
        permission_class=_pc("connection_show"),
        complexity="diagnostic",
        user_input="the server can't resolve DNS — show the active connection profile details",
        notes="Diagnostic: inspect profile DNS settings to trace a resolution failure.",
    ),
    Scenario(
        id="nmcli-connection_show-0004",
        tool="nmcli",
        operation="connection_show",
        permission_class=_pc("connection_show"),
        complexity="multi",
        user_input="show the details of 'bond0-primary' and check if autoconnect is enabled",
        notes="Multi-step: profile inspection then interpret autoconnect setting.",
    ),
    Scenario(
        id="nmcli-connection_show-0005",
        tool="nmcli",
        operation="connection_show",
        permission_class=_pc("connection_show"),
        complexity="single",
        user_input="what IP address and gateway are set on the 'eth0-mgmt' profile?",
        notes="READ: extract IP and gateway from a specific profile.",
    ),

    # =========================================================================
    # connection_add  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_add-0001",
        tool="nmcli",
        operation="connection_add",
        permission_class=_pc("connection_add"),
        complexity="single",
        user_input="create a new ethernet connection profile named 'eth1-static' on eth1",
        notes="WRITE: add a basic ethernet profile on a secondary interface.",
    ),
    Scenario(
        id="nmcli-connection_add-0002",
        tool="nmcli",
        operation="connection_add",
        permission_class=_pc("connection_add"),
        complexity="single",
        user_input="add a static IP connection for eth0 with IP 10.0.1.50/24 and gateway 10.0.1.1",
        notes="WRITE: create a static IP ethernet profile.",
    ),
    Scenario(
        id="nmcli-connection_add-0003",
        tool="nmcli",
        operation="connection_add",
        permission_class=_pc("connection_add"),
        complexity="multi",
        user_input="create a new WiFi connection profile and then bring it up",
        notes="Multi-step: add a wifi profile then activate it.",
    ),
    Scenario(
        id="nmcli-connection_add-0004",
        tool="nmcli",
        operation="connection_add",
        permission_class=_pc("connection_add"),
        complexity="single",
        user_input="add an ethernet profile named 'backup-link' on ens224 with DHCP",
        notes="WRITE: create a DHCP ethernet profile for a backup link.",
    ),
    Scenario(
        id="nmcli-connection_add-0005",
        tool="nmcli",
        operation="connection_add",
        permission_class=_pc("connection_add"),
        complexity="diagnostic",
        user_input="the second NIC has no profile assigned — create one for ens256",
        notes="Diagnostic-triggered WRITE: create profile after identifying unconfigured interface.",
    ),

    # =========================================================================
    # connection_modify  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_modify-0001",
        tool="nmcli",
        operation="connection_modify",
        permission_class=_pc("connection_modify"),
        complexity="single",
        user_input="set the MTU to 9000 on the 'storage-net' connection profile",
        notes="WRITE: configure jumbo frames on a storage network profile.",
    ),
    Scenario(
        id="nmcli-connection_modify-0002",
        tool="nmcli",
        operation="connection_modify",
        permission_class=_pc("connection_modify"),
        complexity="single",
        user_input="disable autoconnect on the 'guest-wifi' profile",
        notes="WRITE: prevent a profile from connecting automatically at boot.",
    ),
    Scenario(
        id="nmcli-connection_modify-0003",
        tool="nmcli",
        operation="connection_modify",
        permission_class=_pc("connection_modify"),
        complexity="multi",
        user_input="change the IP address on 'eth0-static' to 192.168.10.20/24 and then bring it back up",
        notes="Multi-step: modify IP then reactivate the profile.",
    ),
    Scenario(
        id="nmcli-connection_modify-0004",
        tool="nmcli",
        operation="connection_modify",
        permission_class=_pc("connection_modify"),
        complexity="single",
        user_input="set ipv4.route-metric to 100 on the 'Wired connection 1' profile",
        notes="WRITE: adjust route metric to prefer one interface over another.",
    ),
    Scenario(
        id="nmcli-connection_modify-0005",
        tool="nmcli",
        operation="connection_modify",
        permission_class=_pc("connection_modify"),
        complexity="diagnostic",
        user_input="traffic is going out the wrong interface — update the route metric on 'eth1-mgmt'",
        notes="Diagnostic-triggered WRITE: fix routing by adjusting a profile property.",
    ),

    # =========================================================================
    # connection_up  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_up-0001",
        tool="nmcli",
        operation="connection_up",
        permission_class=_pc("connection_up"),
        complexity="single",
        user_input="bring up the 'eth0-static' connection profile",
        notes="WRITE: activate a connection profile on its interface.",
    ),
    Scenario(
        id="nmcli-connection_up-0002",
        tool="nmcli",
        operation="connection_up",
        permission_class=_pc("connection_up"),
        complexity="single",
        user_input="activate the 'backup-link' profile so I have redundancy",
        notes="WRITE: bring up a standby connection profile.",
    ),
    Scenario(
        id="nmcli-connection_up-0003",
        tool="nmcli",
        operation="connection_up",
        permission_class=_pc("connection_up"),
        complexity="multi",
        user_input="activate 'storage-net' and confirm the interface is up",
        notes="Multi-step: bring up then verify connectivity.",
    ),
    Scenario(
        id="nmcli-connection_up-0004",
        tool="nmcli",
        operation="connection_up",
        permission_class=_pc("connection_up"),
        complexity="diagnostic",
        user_input="eth1 is down and the backup traffic is dropping — bring up 'eth1-backup'",
        notes="Diagnostic-triggered WRITE: restore a failed backup link.",
    ),
    Scenario(
        id="nmcli-connection_up-0005",
        tool="nmcli",
        operation="connection_up",
        permission_class=_pc("connection_up"),
        complexity="single",
        user_input="connect the 'ens224-vlan100' profile",
        notes="WRITE: activate a VLAN connection profile.",
    ),

    # =========================================================================
    # connection_down  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_down-0001",
        tool="nmcli",
        operation="connection_down",
        permission_class=_pc("connection_down"),
        complexity="single",
        user_input="bring down the 'guest-wifi' connection profile",
        notes="WRITE: deactivate a profile that is no longer needed.",
    ),
    Scenario(
        id="nmcli-connection_down-0002",
        tool="nmcli",
        operation="connection_down",
        permission_class=_pc("connection_down"),
        complexity="single",
        user_input="disconnect the 'eth1-backup' profile for maintenance",
        notes="WRITE: take a secondary link offline before maintenance.",
    ),
    Scenario(
        id="nmcli-connection_down-0003",
        tool="nmcli",
        operation="connection_down",
        permission_class=_pc("connection_down"),
        complexity="multi",
        user_input="bring down 'ens192-dhcp' and then bring up 'ens192-static' instead",
        notes="Multi-step: swap from DHCP to static profile on the same interface.",
    ),
    Scenario(
        id="nmcli-connection_down-0004",
        tool="nmcli",
        operation="connection_down",
        permission_class=_pc("connection_down"),
        complexity="diagnostic",
        user_input="the storage network profile is conflicting with the mgmt interface — bring it down",
        notes="Diagnostic-triggered WRITE: deactivate a conflicting profile.",
    ),

    # =========================================================================
    # connection_delete  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-connection_delete-0001",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("connection_delete"),
        complexity="single",
        user_input="permanently delete the 'old-vpn' connection profile",
        notes="DESTRUCTIVE: remove a stale VPN profile that is no longer used.",
    ),
    Scenario(
        id="nmcli-connection_delete-0002",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("connection_delete"),
        complexity="single",
        user_input="delete the 'test-dhcp' profile from NetworkManager",
        notes="DESTRUCTIVE: clean up a temporary test profile.",
    ),
    Scenario(
        id="nmcli-connection_delete-0003",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("connection_delete"),
        complexity="multi",
        user_input="show the list of profiles, identify the duplicate, then delete it",
        notes="Multi-step DESTRUCTIVE: diagnose then clean up a duplicate profile.",
    ),
    Scenario(
        id="nmcli-connection_delete-0004",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("connection_delete"),
        complexity="diagnostic",
        user_input="the interface keeps bouncing between two profiles — delete the stale one",
        notes="Diagnostic-triggered DESTRUCTIVE: remove profile causing interface instability.",
    ),
    Scenario(
        id="nmcli-connection_delete-0005",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("connection_delete"),
        complexity="single",
        user_input="remove the 'Wired connection 2' profile permanently",
        notes="DESTRUCTIVE: delete an auto-generated duplicate profile.",
    ),

    # =========================================================================
    # wifi_list  (READ) — 4 entries
    # =========================================================================

    Scenario(
        id="nmcli-wifi_list-0001",
        tool="nmcli",
        operation="wifi_list",
        permission_class=_pc("wifi_list"),
        complexity="single",
        user_input="show me all available Wi-Fi networks",
        notes="READ: scan and list visible Wi-Fi access points.",
    ),
    Scenario(
        id="nmcli-wifi_list-0002",
        tool="nmcli",
        operation="wifi_list",
        permission_class=_pc("wifi_list"),
        complexity="single",
        user_input="what Wi-Fi networks can this server see?",
        notes="READ: inventory of visible SSIDs — useful for troubleshooting.",
    ),
    Scenario(
        id="nmcli-wifi_list-0003",
        tool="nmcli",
        operation="wifi_list",
        permission_class=_pc("wifi_list"),
        complexity="diagnostic",
        user_input="the Wi-Fi keeps dropping — show the available networks and their signal strength",
        notes="Diagnostic: check SSID signal quality to diagnose intermittent drops.",
    ),
    Scenario(
        id="nmcli-wifi_list-0004",
        tool="nmcli",
        operation="wifi_list",
        permission_class=_pc("wifi_list"),
        complexity="multi",
        user_input="list Wi-Fi networks on wlan0 and tell me which have WPA2 security",
        notes="Multi-step: list networks on a specific interface, filter by security.",
    ),

    # =========================================================================
    # wifi_connect  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="nmcli-wifi_connect-0001",
        tool="nmcli",
        operation="wifi_connect",
        permission_class=_pc("wifi_connect"),
        complexity="single",
        user_input="connect to the 'OfficeWifi' network",
        notes="WRITE: join a Wi-Fi network by SSID.",
    ),
    Scenario(
        id="nmcli-wifi_connect-0002",
        tool="nmcli",
        operation="wifi_connect",
        permission_class=_pc("wifi_connect"),
        complexity="single",
        user_input="connect to 'CorpWireless' with the password from the IT wiki",
        notes="WRITE: join a WPA2 network using a passphrase.",
    ),
    Scenario(
        id="nmcli-wifi_connect-0003",
        tool="nmcli",
        operation="wifi_connect",
        permission_class=_pc("wifi_connect"),
        complexity="multi",
        user_input="connect to 'SiteB-Wifi' and then verify the IP was assigned",
        notes="Multi-step: connect then confirm DHCP assignment.",
    ),
    Scenario(
        id="nmcli-wifi_connect-0004",
        tool="nmcli",
        operation="wifi_connect",
        permission_class=_pc("wifi_connect"),
        complexity="diagnostic",
        user_input="the wired link is down — connect to 'EmergencyWifi' as a fallback",
        notes="Diagnostic-triggered WRITE: use Wi-Fi as an emergency management path.",
    ),

    # =========================================================================
    # dns_configure  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nmcli-dns_configure-0001",
        tool="nmcli",
        operation="dns_configure",
        permission_class=_pc("dns_configure"),
        complexity="single",
        user_input="set DNS to 8.8.8.8 and 8.8.4.4 on the 'eth0-static' profile",
        notes="WRITE: configure public DNS servers on a static profile.",
    ),
    Scenario(
        id="nmcli-dns_configure-0002",
        tool="nmcli",
        operation="dns_configure",
        permission_class=_pc("dns_configure"),
        complexity="single",
        user_input="point the 'Wired connection 1' profile at the internal DNS server 10.0.0.53",
        notes="WRITE: switch to an internal/split-horizon DNS server.",
    ),
    Scenario(
        id="nmcli-dns_configure-0003",
        tool="nmcli",
        operation="dns_configure",
        permission_class=_pc("dns_configure"),
        complexity="diagnostic",
        user_input="hostname resolution is failing — set the DNS servers to 1.1.1.1 on the active profile",
        notes="Diagnostic-triggered WRITE: replace unresponsive DNS with a known-good server.",
    ),
    Scenario(
        id="nmcli-dns_configure-0004",
        tool="nmcli",
        operation="dns_configure",
        permission_class=_pc("dns_configure"),
        complexity="multi",
        user_input="set DNS on 'eth0-mgmt' to the company resolvers and then reactivate the profile",
        notes="Multi-step: configure DNS then reconnect so the resolver takes effect.",
    ),
    Scenario(
        id="nmcli-dns_configure-0005",
        tool="nmcli",
        operation="dns_configure",
        permission_class=_pc("dns_configure"),
        complexity="single",
        user_input="configure the 'storage-net' connection to use 192.168.1.1 as its DNS server",
        notes="WRITE: set a dedicated DNS server on a storage network profile.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("nmcli").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "nmcli", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("nmcli").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
