"""finetune/scenarios/network.py — Scenario corpus for the 'network' tool.

All operations and permission_class values are derived LIVE from the
finetune.coreimports registry seam at module import time (INV-schema-sync).
NEVER hardcode an op name that is not validated below, and NEVER hardcode
a permission_class literal — always use _PC[op_name] so that core/ drift
surfaces as a KeyError here rather than a silent corpus corruption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Seam import — INV-read-only-core: only import FROM finetune.coreimports,
# never directly from core/.
# ---------------------------------------------------------------------------
from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Live permission-class lookup.
# _PC maps every real op of 'network' -> its OpClass at import time.
# All Scenario entries reference _PC[op] so that any OpClass change in core/
# is immediately reflected here (INV-schema-sync).
# ---------------------------------------------------------------------------
_net_spec = registry.get("network")
_PC: dict[str, OpClass] = {
    name: spec.permission_class for name, spec in _net_spec.ops.items()
}

# Validate that the ops we author scenarios for actually exist in the registry.
# A typo or stale op name raises KeyError here at import time — loud and early.
_EXPECTED_OPS = {
    "show", "status", "connections", "interfaces",
    "wifi", "bring_up", "bring_down", "set_ip",
}
_MISSING = _EXPECTED_OPS - set(_PC.keys())
assert not _MISSING, (
    f"network ops expected by scenarios but absent from registry: {_MISSING}\n"
    "Update _EXPECTED_OPS or fix the tool registration in core/tools/network.py."
)


# ---------------------------------------------------------------------------
# Scenario dataclass.
# Field names are EXACT and load-bearing — the P1 JOIN aggregator unifies
# all per-tool modules on these exact names.  Do not rename fields.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """A single training-scenario seed for the finetune corpus."""

    id: str
    """Unique scenario id, prefixed with the tool name (e.g. 'network-show-0001')."""

    tool: str
    """Tool name — always 'network' in this module."""

    operation: str
    """Real operation name from the registry (validated against _PC above)."""

    permission_class: OpClass
    """The op's declared OpClass from the live registry (READ/WRITE/DESTRUCTIVE)."""

    complexity: Literal["single", "multi", "diagnostic"]
    """Interaction complexity: single-step, multi-step workflow, or diagnostic."""

    user_input: str
    """Natural English an operator would type. NOT I2-asserted (operator text)."""

    notes: str
    """Free-form authoring notes (not emitted in traces; internal only)."""


# ---------------------------------------------------------------------------
# Scenario corpus — >= 60 entries.
# Spread across all 8 real ops and all 3 complexities.
# WRITE/DESTRUCTIVE entries are honestly labeled so downstream traces teach
# the confirm-before-write gate (INV-permission-fidelity).
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # show — READ (8 scenarios)
    # =========================================================================
    Scenario(
        id="network-show-0001",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="single",
        user_input="show me all IP addresses on this machine",
        notes="Basic read; single-step; expect ip addr output.",
    ),
    Scenario(
        id="network-show-0002",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="single",
        user_input="what IPs does this host have?",
        notes="Synonym phrasing for show.",
    ),
    Scenario(
        id="network-show-0003",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="single",
        user_input="list all network addresses configured on this server",
        notes="More formal operator phrasing.",
    ),
    Scenario(
        id="network-show-0004",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="multi",
        user_input="show me all IP addresses and then tell me which interface has the default route",
        notes="Multi-step: show IPs then route lookup; second step is prose.",
    ),
    Scenario(
        id="network-show-0005",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="diagnostic",
        user_input="the app can't bind to port 443 — check what addresses are actually configured",
        notes="Diagnostic: binding failure prompts address audit.",
    ),
    Scenario(
        id="network-show-0006",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="diagnostic",
        user_input="is there a secondary IP on eth0? the load balancer says it can't find the VIP",
        notes="Diagnostic: missing VIP investigation.",
    ),
    Scenario(
        id="network-show-0007",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="single",
        user_input="display all interface addresses including secondary ones",
        notes="Explicit secondary-address intent.",
    ),
    Scenario(
        id="network-show-0008",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="multi",
        user_input="after we brought up the new VLAN interface, confirm the address is assigned",
        notes="Post-change verification; multi-step context.",
    ),

    # =========================================================================
    # status — READ (8 scenarios)
    # =========================================================================
    Scenario(
        id="network-status-0001",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="single",
        user_input="give me a quick network status",
        notes="Concise single-step brief summary.",
    ),
    Scenario(
        id="network-status-0002",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="single",
        user_input="which interfaces are up right now?",
        notes="Link-state focused phrasing.",
    ),
    Scenario(
        id="network-status-0003",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="single",
        user_input="is eth0 up or down?",
        notes="Single interface state check.",
    ),
    Scenario(
        id="network-status-0004",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="diagnostic",
        user_input="the monitoring system says the host is unreachable — check if the interfaces are up",
        notes="Diagnostic: reachability complaint leads to link check.",
    ),
    Scenario(
        id="network-status-0005",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="diagnostic",
        user_input="we had a power blip — verify all network interfaces came back up",
        notes="Post-event validation.",
    ),
    Scenario(
        id="network-status-0006",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="multi",
        user_input="check network status and flag any interface that doesn't have an IP assigned",
        notes="Multi-step: status then cross-reference with addresses.",
    ),
    Scenario(
        id="network-status-0007",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="single",
        user_input="how many network interfaces does this host have and are they all active?",
        notes="Count and state query.",
    ),
    Scenario(
        id="network-status-0008",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="diagnostic",
        user_input="ens192 isn't responding to pings from outside — confirm the link state",
        notes="Specific interface unresponsive; link check first step.",
    ),

    # =========================================================================
    # connections — READ (8 scenarios)
    # =========================================================================
    Scenario(
        id="network-connections-0001",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="single",
        user_input="list all NetworkManager connection profiles",
        notes="Direct listing request.",
    ),
    Scenario(
        id="network-connections-0002",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="single",
        user_input="what network connections are configured on this box?",
        notes="Operator phrasing for connection list.",
    ),
    Scenario(
        id="network-connections-0003",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="single",
        user_input="show me the nmcli connection profiles",
        notes="Explicit NM reference.",
    ),
    Scenario(
        id="network-connections-0004",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="diagnostic",
        user_input="something created a ghost connection profile — show me all configured connections so I can audit them",
        notes="Security audit: unauthorized connection profile investigation.",
    ),
    Scenario(
        id="network-connections-0005",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="multi",
        user_input="list all connection profiles and tell me which ones are currently active",
        notes="Multi-step: list then filter active.",
    ),
    Scenario(
        id="network-connections-0006",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="diagnostic",
        user_input="the VPN profile keeps disconnecting — check if it's still listed as a connection",
        notes="Diagnostic: VPN profile persistence check.",
    ),
    Scenario(
        id="network-connections-0007",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="single",
        user_input="how many network profiles does NetworkManager know about?",
        notes="Count-focused phrasing.",
    ),
    Scenario(
        id="network-connections-0008",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="diagnostic",
        user_input="after cloning this VM, I see duplicate connection profiles — list them all",
        notes="Post-clone audit; diagnostic complexity.",
    ),

    # =========================================================================
    # interfaces — READ (8 scenarios)
    # =========================================================================
    Scenario(
        id="network-interfaces-0001",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="single",
        user_input="list all network interfaces",
        notes="Direct interface listing.",
    ),
    Scenario(
        id="network-interfaces-0002",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="single",
        user_input="what network devices does this host have?",
        notes="Synonym for interface list.",
    ),
    Scenario(
        id="network-interfaces-0003",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="single",
        user_input="show all NICs on the server",
        notes="NIC-focused phrasing.",
    ),
    Scenario(
        id="network-interfaces-0004",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="diagnostic",
        user_input="I added a second NIC to this VM — verify it shows up in the OS",
        notes="Hardware-addition verification.",
    ),
    Scenario(
        id="network-interfaces-0005",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="diagnostic",
        user_input="the bonding driver should have created bond0 — check if it appears as an interface",
        notes="Diagnostic: kernel bonding interface existence.",
    ),
    Scenario(
        id="network-interfaces-0006",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="multi",
        user_input="list all interfaces and then check which ones have no IP configured",
        notes="Multi-step: interface list then cross-check with addresses.",
    ),
    Scenario(
        id="network-interfaces-0007",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="single",
        user_input="how many network interfaces does this machine have?",
        notes="Count query.",
    ),
    Scenario(
        id="network-interfaces-0008",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="diagnostic",
        user_input="after the kernel update, check that all expected network interfaces are still present",
        notes="Post-update regression check.",
    ),

    # =========================================================================
    # wifi — READ (7 scenarios)
    # =========================================================================
    Scenario(
        id="network-wifi-0001",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="single",
        user_input="what wifi network is this machine connected to?",
        notes="Basic SSID query.",
    ),
    Scenario(
        id="network-wifi-0002",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="single",
        user_input="show me the current wireless SSID",
        notes="Direct SSID request.",
    ),
    Scenario(
        id="network-wifi-0003",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="single",
        user_input="is this host on the corporate wifi or a guest network?",
        notes="Network identity check; useful for security audit.",
    ),
    Scenario(
        id="network-wifi-0004",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="diagnostic",
        user_input="the laptop can't reach internal resources — what network is it connected to?",
        notes="Diagnostic: wrong SSID suspected.",
    ),
    Scenario(
        id="network-wifi-0005",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="diagnostic",
        user_input="after roaming to a new access point, confirm we're still on the right SSID",
        notes="Post-roam SSID confirmation.",
    ),
    Scenario(
        id="network-wifi-0006",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="single",
        user_input="check what wireless network this edge device is using",
        notes="Edge device wireless check.",
    ),
    Scenario(
        id="network-wifi-0007",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="multi",
        user_input="confirm the wifi SSID and then show the associated IP address",
        notes="Multi-step: SSID then IP lookup.",
    ),

    # =========================================================================
    # bring_up — WRITE (9 scenarios)
    # =========================================================================
    Scenario(
        id="network-bring_up-0001",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="single",
        user_input="bring up eth1",
        notes="WRITE — shortest operator form; requires confirmation.",
    ),
    Scenario(
        id="network-bring_up-0002",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="single",
        user_input="enable the ens192 interface",
        notes="WRITE — 'enable' maps to bring_up.",
    ),
    Scenario(
        id="network-bring_up-0003",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="single",
        user_input="activate the 'Management' NetworkManager connection profile",
        notes="WRITE — bring_up via connection name rather than device.",
    ),
    Scenario(
        id="network-bring_up-0004",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="multi",
        user_input="bring up eth1 and then verify it got an IP from DHCP",
        notes="WRITE followed by read check; multi-step.",
    ),
    Scenario(
        id="network-bring_up-0005",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="diagnostic",
        user_input="the backup NIC eth2 is down — bring it up so we can failover traffic",
        notes="WRITE in a failover diagnostic workflow.",
    ),
    Scenario(
        id="network-bring_up-0006",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="single",
        user_input="turn on the ens3 interface",
        notes="WRITE — colloquial 'turn on'.",
    ),
    Scenario(
        id="network-bring_up-0007",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="multi",
        user_input="I just assigned a static IP to ens4 — now bring the interface up to apply it",
        notes="WRITE following a set_ip step.",
    ),
    Scenario(
        id="network-bring_up-0008",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="single",
        user_input="re-enable the 'DMZ' connection profile",
        notes="WRITE — NM profile re-enable scenario.",
    ),
    Scenario(
        id="network-bring_up-0009",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="diagnostic",
        user_input="the VLAN100 interface is showing down after the reboot — bring it up",
        notes="WRITE in a post-reboot recovery diagnostic.",
    ),

    # =========================================================================
    # bring_down — DESTRUCTIVE (8 scenarios)
    # =========================================================================
    Scenario(
        id="network-bring_down-0001",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="single",
        user_input="bring down eth1",
        notes="DESTRUCTIVE — explicit interface down; requires typed DESTROY confirmation.",
    ),
    Scenario(
        id="network-bring_down-0002",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="single",
        user_input="disable the ens192 interface for maintenance",
        notes="DESTRUCTIVE — maintenance window context.",
    ),
    Scenario(
        id="network-bring_down-0003",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="single",
        user_input="shut down the ens3 network interface",
        notes="DESTRUCTIVE — 'shut down' maps to bring_down.",
    ),
    Scenario(
        id="network-bring_down-0004",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="diagnostic",
        user_input="we need to isolate this host from the network for a security investigation — bring down eth0",
        notes="DESTRUCTIVE — security quarantine scenario.",
    ),
    Scenario(
        id="network-bring_down-0005",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="multi",
        user_input="decommission the old management interface: bring down ens160 after verifying ens192 is up",
        notes="DESTRUCTIVE following a read check; multi-step.",
    ),
    Scenario(
        id="network-bring_down-0006",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="single",
        user_input="take ens4 down — it's creating a routing loop",
        notes="DESTRUCTIVE — routing issue remediation.",
    ),
    Scenario(
        id="network-bring_down-0007",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="diagnostic",
        user_input="the storage replication traffic is leaking onto the wrong interface — shut down ens8 to stop it",
        notes="DESTRUCTIVE in a traffic leak diagnostic.",
    ),
    Scenario(
        id="network-bring_down-0008",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="single",
        user_input="turn off the bond0 member ens5 before reconfiguring the bond",
        notes="DESTRUCTIVE — bonding reconfiguration prerequisite.",
    ),

    # =========================================================================
    # set_ip — WRITE (9 scenarios)
    # =========================================================================
    Scenario(
        id="network-set_ip-0001",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="assign 192.168.10.50/24 to eth0",
        notes="WRITE — minimal set_ip with interface and address.",
    ),
    Scenario(
        id="network-set_ip-0002",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="set the IP address of ens192 to 10.0.1.100/24",
        notes="WRITE — explicit 'set the IP' phrasing.",
    ),
    Scenario(
        id="network-set_ip-0003",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="configure a static IP of 172.16.5.20/28 on the 'Server' connection profile",
        notes="WRITE — NM connection profile path.",
    ),
    Scenario(
        id="network-set_ip-0004",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="multi",
        user_input="add a secondary IP 10.10.10.200/24 to eth0 and then verify it's showing up",
        notes="WRITE followed by read verification; multi-step.",
    ),
    Scenario(
        id="network-set_ip-0005",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="diagnostic",
        user_input="the Kubernetes pod network can't reach the host — assign the cluster node IP 10.244.0.1/24 to cni0",
        notes="WRITE in a Kubernetes networking diagnostic.",
    ),
    Scenario(
        id="network-set_ip-0006",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="give ens3 the address 192.0.2.5/30",
        notes="WRITE — colloquial 'give ... the address'.",
    ),
    Scenario(
        id="network-set_ip-0007",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="multi",
        user_input="migrate the VIP: remove the old address and assign 10.50.0.100/16 to ens6",
        notes="WRITE — VIP migration multi-step; this call is the assignment step.",
    ),
    Scenario(
        id="network-set_ip-0008",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="reconfigure ens8 with the new datacenter IP 10.100.0.42/22",
        notes="WRITE — datacenter renumbering scenario.",
    ),
    Scenario(
        id="network-set_ip-0009",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="diagnostic",
        user_input="the floating IP 192.168.1.200/24 for the HA cluster isn't responding — re-assign it to eth0 on this node",
        notes="WRITE in an HA failover diagnostic.",
    ),

    # =========================================================================
    # Additional cross-complexity scenarios for fuller coverage
    # =========================================================================

    # Extra diagnostics spanning multiple ops
    Scenario(
        id="network-show-0009",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="diagnostic",
        user_input="we're getting duplicate IP conflicts on the LAN — show all configured addresses on this host",
        notes="Security/diagnostic: IP conflict investigation.",
    ),
    Scenario(
        id="network-status-0009",
        tool="network",
        operation="status",
        permission_class=_PC["status"],
        complexity="single",
        user_input="quickly check whether all network links are up before the maintenance window",
        notes="Pre-maintenance gate check.",
    ),
    Scenario(
        id="network-connections-0009",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="single",
        user_input="list all NetworkManager profiles including inactive ones",
        notes="Explicit inclusion of inactive profiles.",
    ),
    Scenario(
        id="network-interfaces-0009",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="single",
        user_input="show me the link-layer details for all interfaces",
        notes="MAC address and MTU inspection.",
    ),
    Scenario(
        id="network-wifi-0008",
        tool="network",
        operation="wifi",
        permission_class=_PC["wifi"],
        complexity="diagnostic",
        user_input="the IoT gateway shows intermittent drops — check which wireless network it's associated with",
        notes="Diagnostic: IoT device wireless association.",
    ),
    Scenario(
        id="network-bring_up-0010",
        tool="network",
        operation="bring_up",
        permission_class=_PC["bring_up"],
        complexity="diagnostic",
        user_input="the standby NIC ens9 never came up after the OS reboot — bring it up now",
        notes="WRITE — post-reboot interface recovery.",
    ),
    Scenario(
        id="network-bring_down-0009",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="multi",
        user_input="before swapping the SFP, bring down ens1 so there's no hot-plug issue",
        notes="DESTRUCTIVE — hardware maintenance prerequisite.",
    ),
    Scenario(
        id="network-set_ip-0010",
        tool="network",
        operation="set_ip",
        permission_class=_PC["set_ip"],
        complexity="single",
        user_input="the DHCP lease expired and didn't renew — assign 10.0.0.15/24 to ens3 as a static fallback",
        notes="WRITE — DHCP fallback static assignment.",
    ),

    # Security-hardening and audit scenarios
    Scenario(
        id="network-show-0010",
        tool="network",
        operation="show",
        permission_class=_PC["show"],
        complexity="diagnostic",
        user_input="security audit: enumerate all IP addresses configured on this server",
        notes="Security-hardening audit; read only.",
    ),
    Scenario(
        id="network-interfaces-0010",
        tool="network",
        operation="interfaces",
        permission_class=_PC["interfaces"],
        complexity="diagnostic",
        user_input="hardening review: list all network interfaces so we can identify any unexpected virtual devices",
        notes="Security-hardening: unexpected interface detection.",
    ),
    Scenario(
        id="network-connections-0010",
        tool="network",
        operation="connections",
        permission_class=_PC["connections"],
        complexity="diagnostic",
        user_input="compliance check: list all connection profiles to ensure no unauthorised static configs exist",
        notes="Security-hardening: unauthorised connection audit.",
    ),
    Scenario(
        id="network-bring_down-0010",
        tool="network",
        operation="bring_down",
        permission_class=_PC["bring_down"],
        complexity="diagnostic",
        user_input="this server is being decommissioned — shut down ens0 to isolate it from the production network",
        notes="DESTRUCTIVE — decommission isolation.",
    ),
]

# ---------------------------------------------------------------------------
# Module-level validation — fail loud at import time, not at corpus run time.
# ---------------------------------------------------------------------------
_ids = [s.id for s in SCENARIOS]
_dup_ids = {i for i in _ids if _ids.count(i) > 1}
assert not _dup_ids, f"Duplicate scenario ids in network.py: {_dup_ids}"

assert len(SCENARIOS) >= 60, (
    f"network.py must have >= 60 scenarios, got {len(SCENARIOS)}"
)

for _s in SCENARIOS:
    assert _s.tool == "network", f"Wrong tool on scenario {_s.id}: {_s.tool!r}"
    assert _s.operation in _PC, (
        f"Scenario {_s.id} references unknown op {_s.operation!r}. "
        f"Real ops: {sorted(_PC)}"
    )
    assert _s.permission_class == _PC[_s.operation], (
        f"Scenario {_s.id}: permission_class mismatch for op {_s.operation!r}. "
        f"Registry says {_PC[_s.operation]!r}, scenario has {_s.permission_class!r}. "
        "Always use _PC[op] — never hardcode a permission_class literal."
    )
    assert _s.complexity in {"single", "multi", "diagnostic"}, (
        f"Scenario {_s.id} has invalid complexity {_s.complexity!r}"
    )
