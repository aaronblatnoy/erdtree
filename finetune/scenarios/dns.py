"""finetune/scenarios/dns.py — Scenario corpus for the 'dns' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  resolv_view   READ  — display /etc/resolv.conf
  named_status  READ  — show systemctl status of named (BIND) service
  dig           READ  — DNS record lookup via dig
  nslookup      READ  — DNS lookup via nslookup
  host          READ  — DNS lookup via host utility
  flush_caches  WRITE — flush the local DNS resolver cache via resolvectl

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry)
  so downstream traces teach the confirm-before-write gate.

INV-schema-sync: permission_class is derived from the LIVE registry via
  finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass — fields identical to finetune/scenarios/services.py
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
    """Return the live permission class for a dns operation."""
    return registry.get("dns").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # resolv_view  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="dns-resolv_view-0001",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="single",
        user_input="show me the contents of resolv.conf",
        notes="Direct request to read the resolver configuration file.",
    ),
    Scenario(
        id="dns-resolv_view-0002",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="single",
        user_input="what nameservers is this host using?",
        notes="Admin wants to know the configured DNS servers.",
    ),
    Scenario(
        id="dns-resolv_view-0003",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="single",
        user_input="what search domain is set on this server?",
        notes="Checking the DNS search domain in resolv.conf.",
    ),
    Scenario(
        id="dns-resolv_view-0004",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="diagnostic",
        user_input="DNS lookups are failing — show me resolv.conf so I can check the nameserver config",
        notes="Diagnostic first step: verify resolver configuration when DNS is broken.",
    ),
    Scenario(
        id="dns-resolv_view-0005",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="multi",
        user_input="show resolv.conf and tell me if the nameserver is the expected internal IP",
        notes="Multi-step: read resolv.conf then evaluate the nameserver address.",
    ),
    Scenario(
        id="dns-resolv_view-0006",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="single",
        user_input="cat /etc/resolv.conf",
        notes="Operator typed the raw shell command; mapped to the resolv_view op.",
    ),
    Scenario(
        id="dns-resolv_view-0007",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="diagnostic",
        user_input="the host can't resolve internal hostnames — start by reading resolv.conf",
        notes="Diagnostic: resolv.conf is the first place to check for search-domain issues.",
    ),
    Scenario(
        id="dns-resolv_view-0008",
        tool="dns",
        operation="resolv_view",
        permission_class=_pc("resolv_view"),
        complexity="single",
        user_input="print the resolver configuration for this machine",
        notes="General resolver config inspection.",
    ),

    # =========================================================================
    # named_status  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="dns-named_status-0001",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="single",
        user_input="is named running?",
        notes="Quick health check on the BIND service.",
    ),
    Scenario(
        id="dns-named_status-0002",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="single",
        user_input="check the status of the BIND DNS service",
        notes="Explicit BIND service status request.",
    ),
    Scenario(
        id="dns-named_status-0003",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="diagnostic",
        user_input="clients are getting DNS timeouts — is named up?",
        notes="Diagnostic: verify named is running as part of outage investigation.",
    ),
    Scenario(
        id="dns-named_status-0004",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="single",
        user_input="show the systemctl status of named.service",
        notes="Admin familiar with systemctl commands.",
    ),
    Scenario(
        id="dns-named_status-0005",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="multi",
        user_input="check if named is active and show how long it has been running",
        notes="Multi-step: status then interpret uptime from the output.",
    ),
    Scenario(
        id="dns-named_status-0006",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="diagnostic",
        user_input="the authoritative DNS server seems down — check named",
        notes="Diagnostic: determine if named itself has crashed or stopped.",
    ),
    Scenario(
        id="dns-named_status-0007",
        tool="dns",
        operation="named_status",
        permission_class=_pc("named_status"),
        complexity="single",
        user_input="is the local BIND server active?",
        notes="Check that the local recursive resolver is healthy.",
    ),

    # =========================================================================
    # dig  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="dns-dig-0001",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="look up the A record for example.com",
        notes="Basic forward DNS lookup via dig.",
    ),
    Scenario(
        id="dns-dig-0002",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="what is the MX record for company.com?",
        notes="Mail server record lookup.",
    ),
    Scenario(
        id="dns-dig-0003",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="dig the TXT record for _dmarc.example.com",
        notes="DMARC policy TXT record lookup.",
    ),
    Scenario(
        id="dns-dig-0004",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="resolve the AAAA record for ipv6.example.net",
        notes="IPv6 address record lookup.",
    ),
    Scenario(
        id="dns-dig-0005",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="diagnostic",
        user_input="email delivery is bouncing — check the MX and SPF records for the domain",
        notes="Diagnostic: verify mail records as part of email delivery troubleshooting.",
    ),
    Scenario(
        id="dns-dig-0006",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="multi",
        user_input="look up api.service.local using our internal DNS at 10.10.0.1",
        notes="Multi-step: directed dig query against a specific internal DNS server.",
    ),
    Scenario(
        id="dns-dig-0007",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="dig NS records for example.org",
        notes="Name server record lookup to find authoritative servers.",
    ),
    Scenario(
        id="dns-dig-0008",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="diagnostic",
        user_input="DNS is not resolving app.internal.corp — dig it against the internal resolver at 172.16.0.1",
        notes="Diagnostic: query specific resolver to isolate split-DNS issue.",
    ),
    Scenario(
        id="dns-dig-0009",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="what is the CNAME for www.example.com?",
        notes="CNAME record lookup for a web vhost.",
    ),
    Scenario(
        id="dns-dig-0010",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="multi",
        user_input="dig the A record for db.prod.internal and confirm it resolves to the expected IP",
        notes="Multi-step: resolve then validate the returned address.",
    ),
    Scenario(
        id="dns-dig-0011",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="single",
        user_input="look up the SOA record for example.com",
        notes="Start of Authority record lookup for zone information.",
    ),
    Scenario(
        id="dns-dig-0012",
        tool="dns",
        operation="dig",
        permission_class=_pc("dig"),
        complexity="diagnostic",
        user_input="the certificate renewal failed — check if the DNS challenge TXT record for _acme-challenge.example.com is present",
        notes="Diagnostic: verify ACME challenge TXT record propagation.",
    ),

    # =========================================================================
    # nslookup  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="dns-nslookup-0001",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="single",
        user_input="nslookup example.com",
        notes="Basic nslookup forward resolution.",
    ),
    Scenario(
        id="dns-nslookup-0002",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="single",
        user_input="resolve database.internal using nslookup",
        notes="Internal hostname resolution check.",
    ),
    Scenario(
        id="dns-nslookup-0003",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="diagnostic",
        user_input="the app can't reach payments.internal — can you nslookup it?",
        notes="Diagnostic: verify DNS resolution for an unreachable service.",
    ),
    Scenario(
        id="dns-nslookup-0004",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="single",
        user_input="nslookup api.company.com against our corporate DNS at 10.0.0.1",
        notes="Directed nslookup to a specific DNS server.",
    ),
    Scenario(
        id="dns-nslookup-0005",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="multi",
        user_input="nslookup mail.example.com and check if the address matches what we expect",
        notes="Multi-step: resolve then compare result against expected IP.",
    ),
    Scenario(
        id="dns-nslookup-0006",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="diagnostic",
        user_input="connectivity to the backup server is intermittent — nslookup backup.dc1.internal",
        notes="Diagnostic: check DNS consistency as part of intermittent connection troubleshooting.",
    ),
    Scenario(
        id="dns-nslookup-0007",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="single",
        user_input="do a reverse lookup for 192.168.10.5 with nslookup",
        notes="Reverse DNS lookup of an IP address via nslookup.",
    ),
    Scenario(
        id="dns-nslookup-0008",
        tool="dns",
        operation="nslookup",
        permission_class=_pc("nslookup"),
        complexity="single",
        user_input="use nslookup to check if ldap.corp.internal resolves",
        notes="LDAP endpoint reachability DNS pre-check.",
    ),

    # =========================================================================
    # host  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="dns-host-0001",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="single",
        user_input="host example.com",
        notes="Basic host utility forward resolution.",
    ),
    Scenario(
        id="dns-host-0002",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="single",
        user_input="look up the IP for smtp.example.com using host",
        notes="Mail server address lookup via host.",
    ),
    Scenario(
        id="dns-host-0003",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="diagnostic",
        user_input="outbound email is failing — use host to check smtp.company.com",
        notes="Diagnostic: verify mail relay DNS record.",
    ),
    Scenario(
        id="dns-host-0004",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="single",
        user_input="run host on 10.20.30.40 to get its PTR record",
        notes="Reverse DNS lookup via host utility.",
    ),
    Scenario(
        id="dns-host-0005",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="multi",
        user_input="use host to resolve www.example.com and confirm it returns the load balancer IP",
        notes="Multi-step: resolve and validate address against expected value.",
    ),
    Scenario(
        id="dns-host-0006",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="single",
        user_input="host monitor.internal using the DNS at 10.0.0.53",
        notes="Directed host query to a specific nameserver.",
    ),
    Scenario(
        id="dns-host-0007",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="diagnostic",
        user_input="monitoring alerts say node3.cluster.local is not resolving — check with host",
        notes="Diagnostic: DNS resolution failure reported by monitoring.",
    ),
    Scenario(
        id="dns-host-0008",
        tool="dns",
        operation="host",
        permission_class=_pc("host"),
        complexity="single",
        user_input="what does host return for ntp.example.org?",
        notes="NTP server address lookup.",
    ),

    # =========================================================================
    # flush_caches  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="dns-flush_caches-0001",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="single",
        user_input="flush the DNS cache",
        notes="WRITE: clear local resolver cache — common after a DNS record change.",
    ),
    Scenario(
        id="dns-flush_caches-0002",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="single",
        user_input="clear the local DNS cache so the updated record is picked up",
        notes="WRITE: flush cache after DNS propagation to pick up new record.",
    ),
    Scenario(
        id="dns-flush_caches-0003",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="multi",
        user_input="flush the DNS cache and then re-resolve api.example.com to confirm the new IP is seen",
        notes="Multi-step: flush cache then re-query to verify record update.",
    ),
    Scenario(
        id="dns-flush_caches-0004",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="diagnostic",
        user_input="the service is resolving to the old IP even after the DNS change — flush the cache",
        notes="Diagnostic-triggered WRITE: stale cache causing resolution of old IP.",
    ),
    Scenario(
        id="dns-flush_caches-0005",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="single",
        user_input="resolvectl flush-caches",
        notes="Operator typed the raw resolvectl command; maps to flush_caches op.",
    ),
    Scenario(
        id="dns-flush_caches-0006",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="single",
        user_input="purge the systemd-resolved cache",
        notes="WRITE: clear the systemd-resolved DNS cache via resolvectl.",
    ),
    Scenario(
        id="dns-flush_caches-0007",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="multi",
        user_input="after the failover, flush the DNS cache on this host and verify lookup returns the new server IP",
        notes="Multi-step: post-failover cache flush followed by resolution check.",
    ),
    Scenario(
        id="dns-flush_caches-0008",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("flush_caches"),
        complexity="diagnostic",
        user_input="the TTL has expired but the host is still caching the old address — flush resolver caches",
        notes="Diagnostic: override stuck cached entry by forcing a cache flush.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("dns").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "dns", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("dns").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
