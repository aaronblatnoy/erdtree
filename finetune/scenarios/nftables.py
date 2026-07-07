"""finetune/scenarios/nftables.py — Scenario corpus for the 'nftables' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list_ruleset  READ        — dump the full nft ruleset
  add_rule      WRITE       — add a rule to a chain in a table
  delete_rule   WRITE       — delete a specific rule by handle
  flush_ruleset DESTRUCTIVE — remove all rules, chains, and tables

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE and DESTRUCTIVE scenarios are honestly labeled (permission_class
  from registry) so downstream traces teach the confirm-before-write gate.

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
# Compatible field names are EXACT so the P13 JOIN can unify without renames.
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
    """Return the live permission class for an nftables operation."""
    return registry.get("nftables").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list_ruleset  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="nftables-list_ruleset-0001",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="show me all nftables rules",
        notes="Basic full ruleset dump — the most common inspection command.",
    ),
    Scenario(
        id="nftables-list_ruleset-0002",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="list the current nft ruleset",
        notes="Synonym phrasing for a full ruleset listing.",
    ),
    Scenario(
        id="nftables-list_ruleset-0003",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="what firewall rules are in nftables right now?",
        notes="User asking about active packet-filter rules via nft.",
    ),
    Scenario(
        id="nftables-list_ruleset-0004",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="diagnostic",
        user_input="a service is getting blocked — dump the nftables ruleset so I can see what is filtering it",
        notes="Diagnostic: read the full ruleset to identify which rule is blocking traffic.",
    ),
    Scenario(
        id="nftables-list_ruleset-0005",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="multi",
        user_input="show the nft ruleset and tell me if there are any default-drop policies on the input chain",
        notes="Multi-step: read ruleset then interpret input chain policy.",
    ),
    Scenario(
        id="nftables-list_ruleset-0006",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="print the complete nftables configuration",
        notes="Admin asking for a full configuration snapshot for documentation.",
    ),
    Scenario(
        id="nftables-list_ruleset-0007",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="diagnostic",
        user_input="ssh is getting dropped — show the nftables rules so I can trace the packet path",
        notes="Diagnostic: trace SSH drops through the nft ruleset.",
    ),
    Scenario(
        id="nftables-list_ruleset-0008",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="dump the nft tables and chains",
        notes="Admin wants a structural view of all nft objects.",
    ),
    Scenario(
        id="nftables-list_ruleset-0009",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="multi",
        user_input="list the nftables ruleset and show me how many rules are in the input chain",
        notes="Multi-step: list then count input chain rules.",
    ),
    Scenario(
        id="nftables-list_ruleset-0010",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="diagnostic",
        user_input="outbound traffic to port 443 is failing — check the nft ruleset for any output chain rules blocking it",
        notes="Diagnostic: check output chain rules for an egress problem.",
    ),
    Scenario(
        id="nftables-list_ruleset-0011",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="single",
        user_input="read the raw nft ruleset",
        notes="Technical admin querying the raw nft kernel state.",
    ),
    Scenario(
        id="nftables-list_ruleset-0012",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("list_ruleset"),
        complexity="diagnostic",
        user_input="after the last kernel update the firewall behaviour changed — dump the current nftables ruleset so we can compare it to baseline",
        notes="Post-update audit: compare live ruleset to a known-good baseline.",
    ),

    # =========================================================================
    # add_rule  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="nftables-add_rule-0001",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="allow inbound traffic on TCP port 8080 in the filter input chain",
        notes="WRITE: add an accept rule for a custom application port.",
    ),
    Scenario(
        id="nftables-add_rule-0002",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="add an nft rule to accept SSH traffic on port 22",
        notes="WRITE: explicitly permit SSH in the input chain.",
    ),
    Scenario(
        id="nftables-add_rule-0003",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="block traffic from IP 203.0.113.5 in nftables",
        notes="WRITE: drop rule for a specific source IP.",
    ),
    Scenario(
        id="nftables-add_rule-0004",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="add a rule to accept established and related connections",
        notes="WRITE: stateful connection tracking rule — standard base rule.",
    ),
    Scenario(
        id="nftables-add_rule-0005",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="multi",
        user_input="add an nftables rule to allow port 443 inbound, then verify it appears in the ruleset",
        notes="Multi-step: add rule then list_ruleset to confirm.",
    ),
    Scenario(
        id="nftables-add_rule-0006",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="permit icmp echo-request in nftables so the host is pingable",
        notes="WRITE: allow ICMP ping in the input chain.",
    ),
    Scenario(
        id="nftables-add_rule-0007",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="diagnostic",
        user_input="the monitoring system cannot reach port 9090 — add an nft rule to allow it and tell me the new handle",
        notes="Diagnostic-triggered WRITE: add a rule to unblock a monitoring port.",
    ),
    Scenario(
        id="nftables-add_rule-0008",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="add an nftables rule to drop traffic from the 10.99.0.0/24 subnet",
        notes="WRITE: subnet-level drop rule for a quarantine segment.",
    ),
    Scenario(
        id="nftables-add_rule-0009",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="add a rule to the nat postrouting chain to masquerade traffic from 192.168.1.0/24",
        notes="WRITE: NAT masquerade rule for a private subnet.",
    ),
    Scenario(
        id="nftables-add_rule-0010",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="multi",
        user_input="add an nft accept rule for UDP port 53 on the input chain, then list the ruleset to confirm",
        notes="Multi-step: add DNS allow rule then verify insertion.",
    ),
    Scenario(
        id="nftables-add_rule-0011",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="single",
        user_input="create an nftables rule to rate-limit inbound connections to port 80",
        notes="WRITE: rate-limiting rule on the HTTP input path.",
    ),
    Scenario(
        id="nftables-add_rule-0012",
        tool="nftables",
        operation="add_rule",
        permission_class=_pc("add_rule"),
        complexity="diagnostic",
        user_input="we need to temporarily allow all traffic from 10.0.0.0/8 while troubleshooting — add the nft rule",
        notes="Diagnostic-triggered WRITE: temporary broad allow rule for troubleshooting.",
    ),

    # =========================================================================
    # delete_rule  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="nftables-delete_rule-0001",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="delete nftables rule with handle 5 from the filter input chain",
        notes="WRITE: remove a specific rule by handle — handle identified from prior list.",
    ),
    Scenario(
        id="nftables-delete_rule-0002",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="remove the nft rule with handle 3 that was allowing port 8080",
        notes="WRITE: clean up a rule that is no longer needed.",
    ),
    Scenario(
        id="nftables-delete_rule-0003",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="multi",
        user_input="list the nftables ruleset, identify the rule blocking 203.0.113.5, then delete it",
        notes="Multi-step: inspect ruleset to find handle, then delete the rule.",
    ),
    Scenario(
        id="nftables-delete_rule-0004",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="remove rule handle 7 from the inet filter forward chain",
        notes="WRITE: delete a forward-chain rule by handle.",
    ),
    Scenario(
        id="nftables-delete_rule-0005",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="diagnostic",
        user_input="we accidentally blocked DNS — find and remove the drop rule on UDP port 53 from the input chain",
        notes="Diagnostic: locate and delete an incorrect drop rule that broke DNS.",
    ),
    Scenario(
        id="nftables-delete_rule-0006",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="delete nft rule handle 2 from the nat postrouting chain",
        notes="WRITE: remove a NAT rule by handle.",
    ),
    Scenario(
        id="nftables-delete_rule-0007",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="multi",
        user_input="remove the temporary rule with handle 12 that was added for troubleshooting, then confirm it is gone",
        notes="Multi-step: delete a transient rule then list_ruleset to verify removal.",
    ),
    Scenario(
        id="nftables-delete_rule-0008",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="delete the rate-limit rule with handle 9 from the input chain",
        notes="WRITE: remove a rate-limit rule that is no longer appropriate.",
    ),
    Scenario(
        id="nftables-delete_rule-0009",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="diagnostic",
        user_input="an old block rule for 10.99.0.0/24 is interfering — find its handle and delete it",
        notes="Diagnostic: locate and remove a stale block rule.",
    ),
    Scenario(
        id="nftables-delete_rule-0010",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="single",
        user_input="remove nft input chain rule handle 4 in the ip6 filter table",
        notes="WRITE: delete an IPv6-specific rule by handle.",
    ),
    Scenario(
        id="nftables-delete_rule-0011",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="multi",
        user_input="clean up the nft input chain by deleting rules with handles 10, 11, and 12",
        notes="Multi-step: sequential deletion of multiple stale rules.",
    ),
    Scenario(
        id="nftables-delete_rule-0012",
        tool="nftables",
        operation="delete_rule",
        permission_class=_pc("delete_rule"),
        complexity="diagnostic",
        user_input="a security scan flagged rule handle 6 as overly permissive — delete it from the filter input chain",
        notes="Diagnostic: security-finding-triggered removal of a permissive rule.",
    ),

    # =========================================================================
    # flush_ruleset  (DESTRUCTIVE) — 10 entries
    # =========================================================================

    Scenario(
        id="nftables-flush_ruleset-0001",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="single",
        user_input="flush the entire nftables ruleset",
        notes="DESTRUCTIVE: wipe all tables and rules — operator knows the risk.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0002",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="single",
        user_input="clear all nft rules so I can start fresh",
        notes="DESTRUCTIVE: full ruleset wipe before loading a new baseline configuration.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0003",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="multi",
        user_input="flush the nftables ruleset and then load the new ruleset from /etc/nftables.conf",
        notes="Multi-step DESTRUCTIVE: flush then re-apply configuration from file.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0004",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="diagnostic",
        user_input="nft rules are in an inconsistent state after a failed update — flush everything and re-apply clean rules",
        notes="Diagnostic DESTRUCTIVE: reset a corrupted ruleset to recover a known-good state.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0005",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="single",
        user_input="wipe all nftables rules from the live kernel",
        notes="DESTRUCTIVE: complete kernel ruleset wipe — requires explicit operator confirmation.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0006",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="multi",
        user_input="flush the nftables ruleset, verify it is empty, then restore from backup",
        notes="Multi-step DESTRUCTIVE: flush, verify empty, then restore — rollback procedure.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0007",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="diagnostic",
        user_input="there is a rule conflict causing intermittent drops — flush the entire ruleset as the fastest path to restore service",
        notes="Diagnostic DESTRUCTIVE: emergency reset to remove unknown conflicting rules.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0008",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="single",
        user_input="remove all nftables tables and chains so the kernel has no packet-filter rules",
        notes="DESTRUCTIVE: explicit all-clear of the nft kernel state.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0009",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="multi",
        user_input="flush the nft ruleset during the maintenance window and immediately reload from /etc/nftables.conf",
        notes="Multi-step DESTRUCTIVE: scheduled maintenance window ruleset reload.",
    ),
    Scenario(
        id="nftables-flush_ruleset-0010",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("flush_ruleset"),
        complexity="diagnostic",
        user_input="we are migrating from firewalld to raw nftables — flush the current ruleset before applying the new baseline",
        notes="Diagnostic DESTRUCTIVE: migration step — clear firewalld-generated chains before loading custom nft config.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("nftables").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "nftables", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("nftables").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
