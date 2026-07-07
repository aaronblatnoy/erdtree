"""finetune/scenarios/hostname.py — Scenario corpus for the 'hostname' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status       READ   — show the current hostname and system identity
  set-hostname WRITE  — set the system hostname persistently
  hosts-view   READ   — display the contents of /etc/hosts
  hosts-edit   WRITE  — append an entry to /etc/hosts

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry)
  so downstream traces teach the confirm-before-write gate.

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
    """Return the live permission class for a hostname operation."""
    return registry.get("hostname").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 13 entries
    # =========================================================================

    Scenario(
        id="hostname-status-0001",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the current hostname of this server?",
        notes="Basic hostname lookup — most common admin task.",
    ),
    Scenario(
        id="hostname-status-0002",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the hostname and OS info for this host",
        notes="Read: hostnamectl status output shows OS, kernel, and hostname.",
    ),
    Scenario(
        id="hostname-status-0003",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="display the fully qualified domain name of this machine",
        notes="Read: FQDN visible in hostnamectl status Static hostname field.",
    ),
    Scenario(
        id="hostname-status-0004",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="I need to verify the hostname before updating the SSL certificate — show me hostnamectl output",
        notes="Diagnostic: confirm hostname matches certificate CN before renewal.",
    ),
    Scenario(
        id="hostname-status-0005",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check the hostname and then verify it matches the entry in /etc/hosts",
        notes="Multi-step: status then hosts-view to cross-check consistency.",
    ),
    Scenario(
        id="hostname-status-0006",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="tell me the machine architecture and kernel version from hostnamectl",
        notes="Read: hostnamectl status includes architecture and kernel fields.",
    ),
    Scenario(
        id="hostname-status-0007",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the monitoring system reports a hostname mismatch — show me what hostnamectl says",
        notes="Diagnostic: investigate hostname discrepancy between monitoring and system.",
    ),
    Scenario(
        id="hostname-status-0008",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is this server's static hostname set correctly?",
        notes="Read: confirm static hostname is set (not transient/pretty).",
    ),
    Scenario(
        id="hostname-status-0009",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="after the reboot the hostname looks wrong — run hostnamectl status to check",
        notes="Diagnostic: post-reboot hostname verification.",
    ),
    Scenario(
        id="hostname-status-0010",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me all hostname details including chassis type",
        notes="Read: hostnamectl status shows chassis and hardware vendor fields.",
    ),
    Scenario(
        id="hostname-status-0011",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check the hostname status and then show me if there is a matching entry in /etc/hosts",
        notes="Multi-step: status then hosts-view for full hostname identity audit.",
    ),
    Scenario(
        id="hostname-status-0012",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what operating system version does this server report via hostnamectl?",
        notes="Read: OS version and CPE name visible in hostnamectl status.",
    ),
    Scenario(
        id="hostname-status-0013",
        tool="hostname",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="new server just provisioned — confirm the hostname, OS, and kernel are correct",
        notes="Diagnostic: initial provisioning validation via hostnamectl status.",
    ),

    # =========================================================================
    # set-hostname  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="hostname-set-hostname-0001",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="change the hostname to webserver-01.example.com",
        notes="WRITE: rename the host to match the naming convention.",
    ),
    Scenario(
        id="hostname-set-hostname-0002",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="set the hostname to db-primary.prod.internal",
        notes="WRITE: configure the FQDN for a database primary node.",
    ),
    Scenario(
        id="hostname-set-hostname-0003",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="rename this server to load-balancer-01",
        notes="WRITE: set hostname for a load balancer host.",
    ),
    Scenario(
        id="hostname-set-hostname-0004",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="multi",
        user_input="set the hostname to app-server-03.dc1.company.com and then verify the change took effect",
        notes="Multi-step: set hostname then verify with hostnamectl status.",
    ),
    Scenario(
        id="hostname-set-hostname-0005",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="diagnostic",
        user_input="the server still has the default hostname from the cloud image — set it to monitor-01.ops.example.com",
        notes="Diagnostic-triggered WRITE: fix the default hostname assigned at cloud provisioning.",
    ),
    Scenario(
        id="hostname-set-hostname-0006",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="update the hostname to storage-node-02",
        notes="WRITE: assign a descriptive hostname to a storage node.",
    ),
    Scenario(
        id="hostname-set-hostname-0007",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="set hostname to backup-agent.internal.example.com",
        notes="WRITE: configure FQDN for a backup agent host.",
    ),
    Scenario(
        id="hostname-set-hostname-0008",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="multi",
        user_input="change the hostname to k8s-worker-04.cluster.local and then update /etc/hosts to match",
        notes="Multi-step: set hostname then add the corresponding /etc/hosts entry.",
    ),
    Scenario(
        id="hostname-set-hostname-0009",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="configure the FQDN for this host as dns-secondary.domain.tld",
        notes="WRITE: set hostname for a DNS secondary server.",
    ),
    Scenario(
        id="hostname-set-hostname-0010",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="diagnostic",
        user_input="the Kerberos tickets keep failing because the hostname is wrong — set it to ipa-client.corp.example.com",
        notes="Diagnostic-triggered WRITE: fix hostname to allow Kerberos authentication.",
    ),
    Scenario(
        id="hostname-set-hostname-0011",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="single",
        user_input="rename the server from old-hostname to new-prod-server.example.com",
        notes="WRITE: hostname rename as part of server re-purposing.",
    ),
    Scenario(
        id="hostname-set-hostname-0012",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("set-hostname"),
        complexity="multi",
        user_input="set this machine's hostname to ci-runner-01.build.example.com and confirm the change",
        notes="Multi-step: set hostname for a CI runner then verify the result.",
    ),

    # =========================================================================
    # hosts-view  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="hostname-hosts-view-0001",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="single",
        user_input="show me the contents of /etc/hosts",
        notes="Basic read: display the current hosts file.",
    ),
    Scenario(
        id="hostname-hosts-view-0002",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="single",
        user_input="what entries are in the hosts file?",
        notes="Read: audit the current /etc/hosts for all mappings.",
    ),
    Scenario(
        id="hostname-hosts-view-0003",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="diagnostic",
        user_input="DNS resolution for db-primary is failing — check the /etc/hosts file first",
        notes="Diagnostic: inspect hosts file as first step before checking DNS config.",
    ),
    Scenario(
        id="hostname-hosts-view-0004",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="multi",
        user_input="view /etc/hosts and tell me if 10.0.1.5 has an entry",
        notes="Multi-step: view then interpret — search for a specific IP mapping.",
    ),
    Scenario(
        id="hostname-hosts-view-0005",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="single",
        user_input="display the /etc/hosts file so I can check the loopback entries",
        notes="Read: verify localhost and ::1 loopback lines are correct.",
    ),
    Scenario(
        id="hostname-hosts-view-0006",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="diagnostic",
        user_input="the application cannot resolve internal hostnames — show me /etc/hosts to see what is configured",
        notes="Diagnostic: investigate name resolution failure via hosts file inspection.",
    ),
    Scenario(
        id="hostname-hosts-view-0007",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="single",
        user_input="print out the /etc/hosts file",
        notes="Read: direct display of the hosts database file.",
    ),
    Scenario(
        id="hostname-hosts-view-0008",
        tool="hostname",
        operation="hosts-view",
        permission_class=_pc("hosts-view"),
        complexity="multi",
        user_input="check if there are any duplicate entries in /etc/hosts that might cause resolution conflicts",
        notes="Multi-step: view hosts file then analyse for duplicate IP or hostname entries.",
    ),

    # =========================================================================
    # hosts-edit  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="hostname-hosts-edit-0001",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="add 10.0.1.5 as db-primary.internal to the hosts file",
        notes="WRITE: add a static hostname mapping for an internal database server.",
    ),
    Scenario(
        id="hostname-hosts-edit-0002",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="add an /etc/hosts entry for 192.168.1.100 pointing to cache-01.local",
        notes="WRITE: add a static entry for an internal cache node.",
    ),
    Scenario(
        id="hostname-hosts-edit-0003",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="map 10.10.0.50 to ldap.corp.example.com in /etc/hosts",
        notes="WRITE: add a hosts entry for an LDAP server so DNS is not required.",
    ),
    Scenario(
        id="hostname-hosts-edit-0004",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="multi",
        user_input="add 172.16.0.10 registry.internal to /etc/hosts and then verify the entry was added",
        notes="Multi-step: add hosts entry for a container registry then confirm via hosts-view.",
    ),
    Scenario(
        id="hostname-hosts-edit-0005",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="diagnostic",
        user_input="DNS for ntp-server.internal is not resolving — add a static entry 192.168.10.5 ntp-server.internal to /etc/hosts as a workaround",
        notes="Diagnostic-triggered WRITE: bypass DNS failure by adding a static /etc/hosts entry.",
    ),
    Scenario(
        id="hostname-hosts-edit-0006",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="add a hosts file entry mapping 10.1.2.3 to monitoring.ops.example.com",
        notes="WRITE: static mapping for a monitoring endpoint.",
    ),
    Scenario(
        id="hostname-hosts-edit-0007",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="add 127.0.0.1 test.local to /etc/hosts for local development testing",
        notes="WRITE: loopback entry for a local development hostname.",
    ),
    Scenario(
        id="hostname-hosts-edit-0008",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="multi",
        user_input="map 10.20.30.40 to api-gateway.prod.internal in /etc/hosts and verify the new entry is present",
        notes="Multi-step: add entry then view to confirm it was appended correctly.",
    ),
    Scenario(
        id="hostname-hosts-edit-0009",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="single",
        user_input="add 192.168.50.1 gw.home.local to /etc/hosts",
        notes="WRITE: add a static entry for a home network gateway.",
    ),
    Scenario(
        id="hostname-hosts-edit-0010",
        tool="hostname",
        operation="hosts-edit",
        permission_class=_pc("hosts-edit"),
        complexity="diagnostic",
        user_input="the Ansible controller cannot resolve worker-05 — add 10.0.5.5 worker-05.ansible.local to the hosts file",
        notes="Diagnostic-triggered WRITE: add hosts entry to fix Ansible connectivity to a managed host.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("hostname").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "hostname", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("hostname").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
