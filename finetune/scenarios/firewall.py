"""finetune/scenarios/firewall.py — Scenario corpus for the 'firewall' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list             READ        — show all settings of a firewall zone
  get_zones        READ        — list the defined zones
  query            READ        — query whether a service is allowed in a zone
  add_service      WRITE       — allow a named service in a zone
  add_port         WRITE       — open a port/protocol in a zone
  remove_service   WRITE       — disallow a named service in a zone
  remove_port      WRITE       — close a port/protocol in a zone
  reload           WRITE       — reload the permanent ruleset
  set_default_zone WRITE       — change the default zone
  panic_on         DESTRUCTIVE — drop ALL traffic

Coverage targets
----------------
  >= 60 entries total across all 10 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE and DESTRUCTIVE scenarios are honestly labeled (permission_class from
  registry) so downstream traces teach the confirm-before-write gate.

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
# Compatible field names are EXACT so the P1 JOIN can unify without renames.
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
    """Return the live permission class for a firewall operation."""
    return registry.get("firewall").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="firewall-list-0001",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all firewall rules",
        notes="Basic dump of the active zone's settings.",
    ),
    Scenario(
        id="firewall-list-0002",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what services does the public zone allow?",
        notes="List settings scoped to the public zone.",
    ),
    Scenario(
        id="firewall-list-0003",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list all firewall settings for the dmz zone",
        notes="Operator inspects a named zone.",
    ),
    Scenario(
        id="firewall-list-0004",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show the current firewall settings so I can decide whether to open port 8443",
        notes="Multi: list first, then operator will issue add_port based on output.",
    ),
    Scenario(
        id="firewall-list-0005",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="check the firewall rules for both the public and internal zones",
        notes="Multi-step: list two zones sequentially.",
    ),
    Scenario(
        id="firewall-list-0006",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="clients can't reach port 5432 from outside — what does the firewall look like?",
        notes="Diagnostic: list rules to determine why PostgreSQL is unreachable.",
    ),
    Scenario(
        id="firewall-list-0007",
        tool="firewall",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="we just hardened this box, show me what the firewall is currently allowing",
        notes="Diagnostic: post-hardening audit of allowed services and ports.",
    ),

    # =========================================================================
    # get_zones  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="firewall-get_zones-0001",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="single",
        user_input="what firewall zones are defined on this host?",
        notes="Enumerate all defined zones.",
    ),
    Scenario(
        id="firewall-get_zones-0002",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="single",
        user_input="list all available firewall zones",
        notes="Simple zone inventory.",
    ),
    Scenario(
        id="firewall-get_zones-0003",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="single",
        user_input="how many firewall zones does this server have?",
        notes="Zone count — operator sizing the policy surface.",
    ),
    Scenario(
        id="firewall-get_zones-0004",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="multi",
        user_input="get the list of zones so I can pick one to add the https service to",
        notes="Multi: get_zones to inform an upcoming add_service call.",
    ),
    Scenario(
        id="firewall-get_zones-0005",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="multi",
        user_input="show me all zones, then tell me which ones allow ssh",
        notes="Multi: get_zones first, then query each for ssh — diagnostic chain.",
    ),
    Scenario(
        id="firewall-get_zones-0006",
        tool="firewall",
        operation="get_zones",
        permission_class=_pc("get_zones"),
        complexity="diagnostic",
        user_input="I'm not sure if this machine has a separate zone for the management interface, list all zones",
        notes="Diagnostic: confirm zone topology before issuing a write.",
    ),

    # =========================================================================
    # query  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="firewall-query-0001",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="is SSH allowed through the firewall?",
        notes="Check whether the ssh service is permitted.",
    ),
    Scenario(
        id="firewall-query-0002",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="does the public zone allow http traffic?",
        notes="Query http service in the public zone.",
    ),
    Scenario(
        id="firewall-query-0003",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="check if https is open in the firewall",
        notes="Query https service in the active zone.",
    ),
    Scenario(
        id="firewall-query-0004",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="is MySQL allowed through the firewall on the trusted zone?",
        notes="Zone-scoped service query for MySQL.",
    ),
    Scenario(
        id="firewall-query-0005",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="multi",
        user_input="check if both http and https are allowed in the public zone",
        notes="Multi: query http then https sequentially.",
    ),
    Scenario(
        id="firewall-query-0006",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="multi",
        user_input="verify that ntp is allowed in the internal zone before I add it",
        notes="Multi: query before write — confirm idempotency.",
    ),
    Scenario(
        id="firewall-query-0007",
        tool="firewall",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="a developer says their app on port 8080 can't be reached — is the service registered with the firewall?",
        notes="Diagnostic: query service as part of connectivity troubleshooting.",
    ),

    # =========================================================================
    # add_service  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="firewall-add_service-0001",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="single",
        user_input="allow HTTP through the firewall",
        notes="Permit the http service in the active zone.",
    ),
    Scenario(
        id="firewall-add_service-0002",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="single",
        user_input="open up HTTPS in the public zone",
        notes="Permit https in the public zone.",
    ),
    Scenario(
        id="firewall-add_service-0003",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="single",
        user_input="add the smtp service to the firewall",
        notes="Permit smtp — mail server scenario.",
    ),
    Scenario(
        id="firewall-add_service-0004",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="single",
        user_input="allow the nfs service through the firewall on the internal zone",
        notes="NFS access for internal zone — common data center use.",
    ),
    Scenario(
        id="firewall-add_service-0005",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="multi",
        user_input="I just installed nginx, allow http and https through the firewall",
        notes="Multi: two sequential add_service calls for a new web server.",
    ),
    Scenario(
        id="firewall-add_service-0006",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="multi",
        user_input="add the cockpit management service to the firewall and then reload the rules",
        notes="Multi: add_service followed by reload to make it permanent.",
    ),
    Scenario(
        id="firewall-add_service-0007",
        tool="firewall",
        operation="add_service",
        permission_class=_pc("add_service"),
        complexity="diagnostic",
        user_input="web traffic to this host is being blocked — allow http in the public zone to fix it",
        notes="Diagnostic-driven WRITE: connectivity issue traced to missing http rule.",
    ),

    # =========================================================================
    # add_port  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="firewall-add_port-0001",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="single",
        user_input="open port 8080 TCP in the firewall",
        notes="Open a custom application port.",
    ),
    Scenario(
        id="firewall-add_port-0002",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="single",
        user_input="allow UDP traffic on port 1194 for VPN",
        notes="OpenVPN UDP port.",
    ),
    Scenario(
        id="firewall-add_port-0003",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="single",
        user_input="open port 5432 TCP in the internal zone so the app can reach Postgres",
        notes="Database port in a named zone.",
    ),
    Scenario(
        id="firewall-add_port-0004",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="multi",
        user_input="open ports 9200 and 9300 TCP for Elasticsearch in the internal zone",
        notes="Multi: two add_port calls for the Elasticsearch cluster.",
    ),
    Scenario(
        id="firewall-add_port-0005",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="multi",
        user_input="add port 6443 TCP to the firewall for the Kubernetes API and then reload",
        notes="Multi: add_port then reload.",
    ),
    Scenario(
        id="firewall-add_port-0006",
        tool="firewall",
        operation="add_port",
        permission_class=_pc("add_port"),
        complexity="diagnostic",
        user_input="nothing can connect to our monitoring stack on 9090 — open that port in the public zone",
        notes="Diagnostic-driven: open missing port found during connectivity troubleshooting.",
    ),

    # =========================================================================
    # remove_service  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="firewall-remove_service-0001",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="single",
        user_input="remove the telnet service from the firewall",
        notes="Security hardening: close legacy plaintext service.",
    ),
    Scenario(
        id="firewall-remove_service-0002",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="single",
        user_input="close the ftp service in the public zone",
        notes="Remove FTP from public exposure.",
    ),
    Scenario(
        id="firewall-remove_service-0003",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="single",
        user_input="disallow HTTP in the firewall — this box only serves HTTPS now",
        notes="Migrate web server to TLS-only by removing http.",
    ),
    Scenario(
        id="firewall-remove_service-0004",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="multi",
        user_input="remove http and ftp from the public zone — we're hardening this server",
        notes="Multi: remove two services in a hardening pass.",
    ),
    Scenario(
        id="firewall-remove_service-0005",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="multi",
        user_input="remove the smtp service from the firewall and then reload",
        notes="Multi: remove_service then reload to persist the change.",
    ),
    Scenario(
        id="firewall-remove_service-0006",
        tool="firewall",
        operation="remove_service",
        permission_class=_pc("remove_service"),
        complexity="diagnostic",
        user_input="security audit flagged that cockpit is unnecessarily exposed in the public zone — close it",
        notes="Audit-driven removal of an administrative interface from the wrong zone.",
    ),

    # =========================================================================
    # remove_port  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="firewall-remove_port-0001",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="single",
        user_input="close port 8080 TCP in the firewall",
        notes="Close a temporary development port.",
    ),
    Scenario(
        id="firewall-remove_port-0002",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="single",
        user_input="remove UDP port 1194 from the firewall, we shut down the VPN",
        notes="Clean up after a decommissioned service.",
    ),
    Scenario(
        id="firewall-remove_port-0003",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="single",
        user_input="close port 3000 TCP in the public zone — the dev app was deployed there by mistake",
        notes="Unintended port exposure remediation.",
    ),
    Scenario(
        id="firewall-remove_port-0004",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="multi",
        user_input="close ports 9200 and 9300 TCP in the internal zone, we moved Elasticsearch off this host",
        notes="Multi: two remove_port calls after service migration.",
    ),
    Scenario(
        id="firewall-remove_port-0005",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="multi",
        user_input="remove port 8443 from the firewall and reload the rules",
        notes="Multi: remove_port then reload.",
    ),
    Scenario(
        id="firewall-remove_port-0006",
        tool="firewall",
        operation="remove_port",
        permission_class=_pc("remove_port"),
        complexity="diagnostic",
        user_input="a scan found port 4000 TCP unexpectedly open — close it",
        notes="Diagnostic: close an unexpected port found during a security scan.",
    ),

    # =========================================================================
    # reload  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="firewall-reload-0001",
        tool="firewall",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="reload the firewall rules",
        notes="Apply permanent rule changes without dropping connections.",
    ),
    Scenario(
        id="firewall-reload-0002",
        tool="firewall",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="make the firewall changes permanent — reload the ruleset",
        notes="Explicit operator intent to persist runtime changes.",
    ),
    Scenario(
        id="firewall-reload-0003",
        tool="firewall",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="multi",
        user_input="I edited the firewall config files directly, reload to pick them up",
        notes="Multi: manual config edit followed by reload.",
    ),
    Scenario(
        id="firewall-reload-0004",
        tool="firewall",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="multi",
        user_input="after adding all those services, reload the firewall to make sure they stick",
        notes="Multi: reload to finalise a batch of add_service operations.",
    ),
    Scenario(
        id="firewall-reload-0005",
        tool="firewall",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="diagnostic",
        user_input="the firewall seems to have drifted from what I configured — reload from the permanent ruleset",
        notes="Diagnostic: restore permanent config by reloading after runtime drift.",
    ),

    # =========================================================================
    # set_default_zone  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="firewall-set_default_zone-0001",
        tool="firewall",
        operation="set_default_zone",
        permission_class=_pc("set_default_zone"),
        complexity="single",
        user_input="set the default firewall zone to internal",
        notes="Change the default zone to a more restrictive one.",
    ),
    Scenario(
        id="firewall-set_default_zone-0002",
        tool="firewall",
        operation="set_default_zone",
        permission_class=_pc("set_default_zone"),
        complexity="single",
        user_input="make 'drop' the default firewall zone",
        notes="Maximally restrictive default — deny all inbound by default.",
    ),
    Scenario(
        id="firewall-set_default_zone-0003",
        tool="firewall",
        operation="set_default_zone",
        permission_class=_pc("set_default_zone"),
        complexity="single",
        user_input="change the default firewall zone to trusted",
        notes="Change to trusted zone — appropriate for a fully internal host.",
    ),
    Scenario(
        id="firewall-set_default_zone-0004",
        tool="firewall",
        operation="set_default_zone",
        permission_class=_pc("set_default_zone"),
        complexity="multi",
        user_input="list all zones first, then set the default to the most restrictive one available",
        notes="Multi: get_zones to inform, then set_default_zone.",
    ),
    Scenario(
        id="firewall-set_default_zone-0005",
        tool="firewall",
        operation="set_default_zone",
        permission_class=_pc("set_default_zone"),
        complexity="diagnostic",
        user_input="new interfaces are picking up the wrong zone — set the default to internal to fix it",
        notes="Diagnostic: misconfigured default zone causing unexpected exposure for new NICs.",
    ),

    # =========================================================================
    # panic_on  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="firewall-panic_on-0001",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("panic_on"),
        complexity="single",
        user_input="turn on firewall panic mode right now — we're being attacked",
        notes="Incident response: drop all traffic immediately.",
    ),
    Scenario(
        id="firewall-panic_on-0002",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("panic_on"),
        complexity="single",
        user_input="enable panic mode on the firewall, I need to cut all network traffic",
        notes="Deliberate isolation of a compromised host.",
    ),
    Scenario(
        id="firewall-panic_on-0003",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("panic_on"),
        complexity="single",
        user_input="put the firewall into panic mode to stop a data exfiltration attempt",
        notes="Security incident: stop outbound exfiltration by dropping all traffic.",
    ),
    Scenario(
        id="firewall-panic_on-0004",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("panic_on"),
        complexity="multi",
        user_input="we detected unusual outbound traffic — first show the firewall rules, then enable panic mode",
        notes="Multi: list rules to confirm the anomaly, then panic_on as containment.",
    ),
    Scenario(
        id="firewall-panic_on-0005",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("panic_on"),
        complexity="diagnostic",
        user_input="network monitoring shows this box is scanning other hosts internally — isolate it by enabling panic mode",
        notes="Diagnostic: host identified as compromised internal scanner; panic_on as containment.",
    ),

]
