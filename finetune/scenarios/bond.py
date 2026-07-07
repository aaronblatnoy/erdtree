"""finetune/scenarios/bond.py — Scenario corpus for the 'bond' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  show    READ        — list bond connections or show detail for a named bond
  add     WRITE       — create a bond connection
  modify  WRITE       — modify a property on an existing bond connection
  remove  DESTRUCTIVE — delete a bond connection (nmcli connection delete)

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE and DESTRUCTIVE scenarios are honestly labeled (permission_class
  from registry) so downstream traces teach the confirm-before-write and
  destructive-gate flows.

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
# Compatible field names are EXACT so the Phase-13 JOIN can unify them.
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
    """Return the live permission class for a bond operation."""
    return registry.get("bond").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # show  (READ) — 14 entries
    # =========================================================================

    Scenario(
        id="bond-show-0001",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="list all bond interfaces on this host",
        notes="Show all NM connections to identify bonds.",
    ),
    Scenario(
        id="bond-show-0002",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="show me the details of bond0",
        notes="Detailed inspection of a specific bond connection.",
    ),
    Scenario(
        id="bond-show-0003",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="what bonding mode is bond0 using?",
        notes="Read bond.options from the connection profile.",
    ),
    Scenario(
        id="bond-show-0004",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="show the current configuration of the bond1 interface",
        notes="Inspect second bond interface.",
    ),
    Scenario(
        id="bond-show-0005",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="display all network bond connections",
        notes="List all bond-type NM connections.",
    ),
    Scenario(
        id="bond-show-0006",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="what interfaces are members of bond0?",
        notes="Check slave/port membership of a bond.",
    ),
    Scenario(
        id="bond-show-0007",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="multi",
        user_input="show bond0 details and then tell me if it is currently active",
        notes="Multi-step: show then interpret GENERAL.STATE from output.",
    ),
    Scenario(
        id="bond-show-0008",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="multi",
        user_input="list all bonds and then show the full config of bond0",
        notes="Multi-step: list then detail.",
    ),
    Scenario(
        id="bond-show-0009",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="diagnostic",
        user_input="the server lost network access — check which bonds are configured and whether bond0 is up",
        notes="Diagnostic: inspect bond state during a network outage.",
    ),
    Scenario(
        id="bond-show-0010",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="diagnostic",
        user_input="network throughput is lower than expected — show me the bond configuration to check the mode",
        notes="Diagnostic: inspect bond mode for performance issues.",
    ),
    Scenario(
        id="bond-show-0011",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="diagnostic",
        user_input="after the last change bond0 is not passing traffic — show its full properties",
        notes="Diagnostic: post-change inspection of bond profile.",
    ),
    Scenario(
        id="bond-show-0012",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="show the miimon setting on bond0",
        notes="Read MII monitoring interval from bond.options.",
    ),
    Scenario(
        id="bond-show-0013",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="single",
        user_input="what IP address is assigned to bond0?",
        notes="Inspect ipv4.addresses from the bond profile.",
    ),
    Scenario(
        id="bond-show-0014",
        tool="bond",
        operation="show",
        permission_class=_pc("show"),
        complexity="multi",
        user_input="show all bond connections and for each one tell me whether it is 802.3ad or active-backup mode",
        notes="Multi-step: list bonds then classify each by mode.",
    ),

    # =========================================================================
    # add  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="bond-add-0001",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create a bond interface called bond0 in active-backup mode",
        notes="WRITE: basic bond creation in the most common mode.",
    ),
    Scenario(
        id="bond-add-0002",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="set up a new bond0 using 802.3ad (LACP) mode",
        notes="WRITE: create bond for LACP aggregation.",
    ),
    Scenario(
        id="bond-add-0003",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create bond1 with round-robin load balancing",
        notes="WRITE: balance-rr bonding mode.",
    ),
    Scenario(
        id="bond-add-0004",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="add a new bond interface named bond2",
        notes="WRITE: create bond with default active-backup mode.",
    ),
    Scenario(
        id="bond-add-0005",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create a high-availability bond called bond0 using active-backup",
        notes="WRITE: HA bond creation — typical data-center use case.",
    ),
    Scenario(
        id="bond-add-0006",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="set up bond0 with balance-tlb adaptive load balancing",
        notes="WRITE: adaptive transmit load balancing bond.",
    ),
    Scenario(
        id="bond-add-0007",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="multi",
        user_input="create bond0 in active-backup mode and then verify it was added successfully",
        notes="Multi-step: create then show to verify.",
    ),
    Scenario(
        id="bond-add-0008",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="multi",
        user_input="create bond1 using 802.3ad then check its configuration",
        notes="Multi-step: create LACP bond then inspect.",
    ),
    Scenario(
        id="bond-add-0009",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="multi",
        user_input="create a bond0 interface and then add eth0 and eth1 as member ports",
        notes="Multi-step: bond creation followed by slave attachment operations.",
    ),
    Scenario(
        id="bond-add-0010",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="diagnostic",
        user_input="the server only has one active NIC — set up bond0 in active-backup mode so we can add a second later",
        notes="Diagnostic-triggered WRITE: create bond in preparation for redundancy.",
    ),
    Scenario(
        id="bond-add-0011",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="diagnostic",
        user_input="we need LACP aggregation for this host — create bond0 with 802.3ad",
        notes="Diagnostic-triggered WRITE: LACP bond for throughput improvement.",
    ),
    Scenario(
        id="bond-add-0012",
        tool="bond",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create a bond named bond0 using balance-alb mode",
        notes="WRITE: adaptive load balancing bond creation.",
    ),

    # =========================================================================
    # modify  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="bond-modify-0001",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="change bond0 to use 802.3ad (LACP) mode",
        notes="WRITE: change bonding mode on an existing bond.",
    ),
    Scenario(
        id="bond-modify-0002",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="set the miimon interval on bond0 to 200ms",
        notes="WRITE: tune MII monitoring interval for failure detection.",
    ),
    Scenario(
        id="bond-modify-0003",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="assign the IP address 10.0.0.5/24 to bond0",
        notes="WRITE: set static IP on the bond connection.",
    ),
    Scenario(
        id="bond-modify-0004",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="set the default gateway for bond0 to 10.0.0.1",
        notes="WRITE: configure gateway on the bond profile.",
    ),
    Scenario(
        id="bond-modify-0005",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="disable autoconnect on bond0",
        notes="WRITE: set connection.autoconnect to no.",
    ),
    Scenario(
        id="bond-modify-0006",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="multi",
        user_input="change bond0 from active-backup to 802.3ad and then show the updated config",
        notes="Multi-step: modify mode then verify with show.",
    ),
    Scenario(
        id="bond-modify-0007",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="multi",
        user_input="update the miimon on bond0 to 100 and the updelay to 200",
        notes="Multi-step: apply two bond.options changes sequentially.",
    ),
    Scenario(
        id="bond-modify-0008",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="diagnostic",
        user_input="bond0 is failing over slowly — increase the miimon to 50ms and downdelay to 200ms",
        notes="Diagnostic-triggered WRITE: tune failover timing parameters.",
    ),
    Scenario(
        id="bond-modify-0009",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="diagnostic",
        user_input="the team changed switch config to support LACP — update bond0 to 802.3ad mode",
        notes="Diagnostic-triggered WRITE: mode change following switch reconfiguration.",
    ),
    Scenario(
        id="bond-modify-0010",
        tool="bond",
        operation="modify",
        permission_class=_pc("modify"),
        complexity="single",
        user_input="set bond0 to use DHCP for IPv4",
        notes="WRITE: switch bond from static to DHCP addressing.",
    ),

    # =========================================================================
    # remove  (DESTRUCTIVE) — 10 entries
    # =========================================================================

    Scenario(
        id="bond-remove-0001",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="delete the bond0 interface",
        notes="DESTRUCTIVE: remove bond connection — drops aggregated link.",
    ),
    Scenario(
        id="bond-remove-0002",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove bond1 from this host",
        notes="DESTRUCTIVE: remove a non-primary bond connection.",
    ),
    Scenario(
        id="bond-remove-0003",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="tear down bond0 — we are replacing it with a single-interface config",
        notes="DESTRUCTIVE: remove bond as part of network reconfiguration.",
    ),
    Scenario(
        id="bond-remove-0004",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="decommission bond0 on this server",
        notes="DESTRUCTIVE: decommission-time bond removal.",
    ),
    Scenario(
        id="bond-remove-0005",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="show the current bond0 config and then delete it",
        notes="Multi-step: inspect then remove the bond connection.",
    ),
    Scenario(
        id="bond-remove-0006",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="remove bond0 and then confirm it no longer appears in the connection list",
        notes="Multi-step: remove bond then verify deletion with show.",
    ),
    Scenario(
        id="bond-remove-0007",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="bond0 is misconfigured and causing a network loop — remove it immediately",
        notes="Diagnostic-triggered DESTRUCTIVE: emergency bond removal for a network loop.",
    ),
    Scenario(
        id="bond-remove-0008",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="the old bond0 is conflicting with the new bonding config — delete it so we can recreate it",
        notes="Diagnostic-triggered DESTRUCTIVE: remove stale bond before re-creation.",
    ),
    Scenario(
        id="bond-remove-0009",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="list all bonds and remove any that are no longer in use",
        notes="Multi-step: list bonds then selectively remove inactive ones.",
    ),
    Scenario(
        id="bond-remove-0010",
        tool="bond",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="the switch port team was dissolved — remove bond0 since those ports are now individual links",
        notes="Diagnostic-triggered DESTRUCTIVE: remove bond after physical topology change.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("bond").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "bond", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("bond").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
