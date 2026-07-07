"""finetune/scenarios/routing.py — Scenario corpus for the 'routing' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  route_show         READ        — display the IP routing table
  route_add          WRITE       — add a static route
  route_del          WRITE       — delete a route (advisory; Phase 1 classifier
                                   escalates 'ip route del default' to DESTRUCTIVE)
  route_flush        DESTRUCTIVE — flush all routes in a routing table
  policy_rule_show   READ        — show IP policy routing rules
  policy_rule_add    WRITE       — add an IP policy routing rule
  policy_rule_flush  DESTRUCTIVE — flush all policy routing rules

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.
  Permission classes derived live from the registry (INV-schema-sync).

INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass
# Field names are EXACT so the Phase-13 JOIN can normalise without renames.
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
    """Return the live permission class for a routing operation."""
    return registry.get("routing").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # route_show  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="routing-route_show-0001",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="single",
        user_input="show me the current routing table",
        notes="Simple read: display all routes in the default routing table.",
    ),
    Scenario(
        id="routing-route_show-0002",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="single",
        user_input="what routes does this host know about?",
        notes="Read: list all known routes for network audit.",
    ),
    Scenario(
        id="routing-route_show-0003",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="single",
        user_input="display the main routing table",
        notes="Read: explicitly request the main table.",
    ),
    Scenario(
        id="routing-route_show-0004",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="single",
        user_input="show me what routes are in table 100",
        notes="Read: query a numbered policy routing table.",
    ),
    Scenario(
        id="routing-route_show-0005",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="diagnostic",
        user_input="traffic to 10.20.0.0/16 is not arriving — show the routing table so I can check if there is a route",
        notes="Diagnostic: inspect routes to troubleshoot missing path.",
    ),
    Scenario(
        id="routing-route_show-0006",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="multi",
        user_input="show the routing table and tell me if there is a default gateway configured",
        notes="Multi: read routes then interpret for default gateway presence.",
    ),
    Scenario(
        id="routing-route_show-0007",
        tool="routing",
        operation="route_show",
        permission_class=_pc("route_show"),
        complexity="diagnostic",
        user_input="the server cannot reach the internet — check the routing table first",
        notes="Diagnostic: start connectivity triage by reviewing routes.",
    ),

    # =========================================================================
    # route_add  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="routing-route_add-0001",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="single",
        user_input="add a route to 192.168.50.0/24 via 10.0.0.1",
        notes="WRITE: add a static route to a remote subnet via a gateway.",
    ),
    Scenario(
        id="routing-route_add-0002",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="single",
        user_input="add a default route via 10.0.0.254",
        notes="WRITE: add a default gateway route.",
    ),
    Scenario(
        id="routing-route_add-0003",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="single",
        user_input="route traffic for 172.16.0.0/12 through eth1",
        notes="WRITE: add a route pinned to a specific interface.",
    ),
    Scenario(
        id="routing-route_add-0004",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="multi",
        user_input="add a route to 10.50.0.0/16 via 10.0.0.1 with metric 200 and then verify it shows up in the routing table",
        notes="Multi: add route then confirm with route_show.",
    ),
    Scenario(
        id="routing-route_add-0005",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="diagnostic",
        user_input="the VPN subnet 172.31.0.0/16 is unreachable — add a static route pointing to the VPN gateway 10.8.0.1",
        notes="Diagnostic-triggered WRITE: add missing route to fix connectivity.",
    ),
    Scenario(
        id="routing-route_add-0006",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="single",
        user_input="add a route to 192.168.1.0/24 via 10.0.0.1 with metric 100",
        notes="WRITE: add a route with explicit metric for failover configuration.",
    ),
    Scenario(
        id="routing-route_add-0007",
        tool="routing",
        operation="route_add",
        permission_class=_pc("route_add"),
        complexity="single",
        user_input="create a static route for the management network 10.100.0.0/24 through the management gateway 10.100.0.254",
        notes="WRITE: add a dedicated management network route.",
    ),

    # =========================================================================
    # route_del  (WRITE advisory — Phase 1 escalates del default to DESTRUCTIVE)
    # 7 entries
    # =========================================================================

    Scenario(
        id="routing-route_del-0001",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="single",
        user_input="remove the route to 192.168.50.0/24",
        notes="WRITE: delete a specific subnet route; advisory class per table.",
    ),
    Scenario(
        id="routing-route_del-0002",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="single",
        user_input="delete the static route for 10.50.0.0/16",
        notes="WRITE: remove a previously added static route.",
    ),
    Scenario(
        id="routing-route_del-0003",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="single",
        user_input="remove the default route — we are switching gateways",
        notes="WRITE (advisory; Phase 1 escalates 'ip route del default' to DESTRUCTIVE): deleting the default route severs all remote connectivity.",
    ),
    Scenario(
        id="routing-route_del-0004",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="multi",
        user_input="delete the old route to 172.16.0.0/12 and add a new one via the updated gateway 10.0.1.1",
        notes="Multi: delete stale route then add replacement.",
    ),
    Scenario(
        id="routing-route_del-0005",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="diagnostic",
        user_input="there is a duplicate route to 10.20.0.0/16 causing asymmetric routing — remove the less preferred one via 10.0.0.2",
        notes="Diagnostic-triggered WRITE: remove conflicting route to fix asymmetric routing.",
    ),
    Scenario(
        id="routing-route_del-0006",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="single",
        user_input="clean up the old management route to 10.100.0.0/24",
        notes="WRITE: delete a no-longer-needed management subnet route.",
    ),
    Scenario(
        id="routing-route_del-0007",
        tool="routing",
        operation="route_del",
        permission_class=_pc("route_del"),
        complexity="single",
        user_input="remove the route to 192.168.200.0/24 that goes through eth2",
        notes="WRITE: interface-scoped route deletion to match a specific nexthop.",
    ),

    # =========================================================================
    # route_flush  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="routing-route_flush-0001",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="single",
        user_input="flush all routes in routing table 100",
        notes="DESTRUCTIVE: wipe a custom policy routing table.",
    ),
    Scenario(
        id="routing-route_flush-0002",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="single",
        user_input="clear all entries from routing table 200",
        notes="DESTRUCTIVE: flush a numbered routing table used for policy routing.",
    ),
    Scenario(
        id="routing-route_flush-0003",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="multi",
        user_input="flush table 100 and then re-add the correct routes from the runbook",
        notes="Multi: destructive flush followed by rebuilding the table.",
    ),
    Scenario(
        id="routing-route_flush-0004",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="diagnostic",
        user_input="the policy routes in table 150 are corrupted after a failed migration — flush the table so we can start fresh",
        notes="Diagnostic-triggered DESTRUCTIVE: flush corrupted policy table as recovery step.",
    ),
    Scenario(
        id="routing-route_flush-0005",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="single",
        user_input="wipe table 300 — it is no longer in use",
        notes="DESTRUCTIVE: flush an unused routing table during cleanup.",
    ),
    Scenario(
        id="routing-route_flush-0006",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("route_flush"),
        complexity="single",
        user_input="flush routing table 50 before repopulating it from the new config",
        notes="DESTRUCTIVE: pre-flush before reconfiguration to avoid stale routes.",
    ),

    # =========================================================================
    # policy_rule_show  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="routing-policy_rule_show-0001",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="single",
        user_input="show me all the IP policy rules on this host",
        notes="Read: list all policy routing rules.",
    ),
    Scenario(
        id="routing-policy_rule_show-0002",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="single",
        user_input="what policy routing rules are configured?",
        notes="Read: enumerate policy rules for audit.",
    ),
    Scenario(
        id="routing-policy_rule_show-0003",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="diagnostic",
        user_input="traffic from the 10.1.0.0/24 network is routing incorrectly — show the policy rules",
        notes="Diagnostic: inspect policy rules to find the cause of incorrect routing.",
    ),
    Scenario(
        id="routing-policy_rule_show-0004",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="multi",
        user_input="list the policy rules and tell me which ones reference table 100",
        notes="Multi: show rules then filter by table reference.",
    ),
    Scenario(
        id="routing-policy_rule_show-0005",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="diagnostic",
        user_input="I added policy rules yesterday but I am not sure they took effect — list them",
        notes="Diagnostic: verify that policy rules were applied correctly.",
    ),
    Scenario(
        id="routing-policy_rule_show-0006",
        tool="routing",
        operation="policy_rule_show",
        permission_class=_pc("policy_rule_show"),
        complexity="single",
        user_input="print the ip rule list",
        notes="Read: direct request for ip rule output.",
    ),

    # =========================================================================
    # policy_rule_add  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="routing-policy_rule_add-0001",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="single",
        user_input="add a policy rule to route traffic from 10.1.0.0/24 via table 100",
        notes="WRITE: add a source-based policy rule.",
    ),
    Scenario(
        id="routing-policy_rule_add-0002",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="single",
        user_input="create a policy routing rule with priority 200 that sends traffic from 192.168.10.0/24 to table 200",
        notes="WRITE: add a priority-numbered policy rule.",
    ),
    Scenario(
        id="routing-policy_rule_add-0003",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="multi",
        user_input="add a policy rule for traffic from 10.2.0.0/24 to use table 150, then verify it appears in the rule list",
        notes="Multi: add rule then confirm with policy_rule_show.",
    ),
    Scenario(
        id="routing-policy_rule_add-0004",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="diagnostic",
        user_input="multi-homed server is sending replies out the wrong interface — add a policy rule so traffic from 203.0.113.5 uses table 300",
        notes="Diagnostic-triggered WRITE: fix asymmetric routing on a multi-homed host.",
    ),
    Scenario(
        id="routing-policy_rule_add-0005",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="single",
        user_input="add a policy rule with priority 100 sending all traffic from the VPN subnet 10.8.0.0/16 to table 50",
        notes="WRITE: VPN traffic steering via policy rule.",
    ),
    Scenario(
        id="routing-policy_rule_add-0006",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="single",
        user_input="insert a policy routing rule for traffic destined to 172.16.0.0/12 to look up table 100",
        notes="WRITE: destination-based policy routing rule.",
    ),
    Scenario(
        id="routing-policy_rule_add-0007",
        tool="routing",
        operation="policy_rule_add",
        permission_class=_pc("policy_rule_add"),
        complexity="multi",
        user_input="configure policy-based routing for the management interface: add a rule for 10.100.0.0/24 with priority 50 pointing to table 200, then show the rules to confirm",
        notes="Multi: add management-network policy rule then verify.",
    ),

    # =========================================================================
    # policy_rule_flush  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="routing-policy_rule_flush-0001",
        tool="routing",
        operation="policy_rule_flush",
        permission_class=_pc("policy_rule_flush"),
        complexity="single",
        user_input="flush all policy routing rules",
        notes="DESTRUCTIVE: wipe all ip rules; can break routing and sever access.",
    ),
    Scenario(
        id="routing-policy_rule_flush-0002",
        tool="routing",
        operation="policy_rule_flush",
        permission_class=_pc("policy_rule_flush"),
        complexity="diagnostic",
        user_input="the policy rules are in a broken state after a botched config push — flush them all so I can start over",
        notes="Diagnostic-triggered DESTRUCTIVE: flush all rules to recover from bad state.",
    ),
    Scenario(
        id="routing-policy_rule_flush-0003",
        tool="routing",
        operation="policy_rule_flush",
        permission_class=_pc("policy_rule_flush"),
        complexity="multi",
        user_input="flush all policy rules and then re-add only the ones we need from the config file",
        notes="Multi: destructive flush then selective rebuild.",
    ),
    Scenario(
        id="routing-policy_rule_flush-0004",
        tool="routing",
        operation="policy_rule_flush",
        permission_class=_pc("policy_rule_flush"),
        complexity="single",
        user_input="clear all ip policy rules as part of decommissioning this host's multi-homed setup",
        notes="DESTRUCTIVE: remove all policy rules during host decommission.",
    ),
    Scenario(
        id="routing-policy_rule_flush-0005",
        tool="routing",
        operation="policy_rule_flush",
        permission_class=_pc("policy_rule_flush"),
        complexity="diagnostic",
        user_input="something is wrong with the policy routing — just wipe all the ip rules and let the defaults take over",
        notes="Diagnostic-triggered DESTRUCTIVE: last-resort flush to restore default routing behaviour.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("routing").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "routing", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("routing").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
