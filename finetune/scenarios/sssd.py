"""finetune/scenarios/sssd.py — Scenario corpus for the 'sssd' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status      READ        — show the running status of the sssd daemon
  id_lookup   READ        — look up a user or group identity via NSS/sssd
  cache_flush  WRITE      — flush the sssd cache (sss_cache -E)
  realm_list  READ        — list enrolled or discovered realms
  realm_join  WRITE       — enroll this host into an AD/IdM domain
  realm_leave DESTRUCTIVE — remove this host from an AD/IdM domain

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so traces teach the confirm gate.

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
# Scenario dataclass — identical field names to services.py for JOIN compat
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
    """Return the live permission class for an sssd operation."""
    return registry.get("sssd").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="sssd-status-0001",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is sssd running?",
        notes="Simple health check on the sssd daemon.",
    ),
    Scenario(
        id="sssd-status-0002",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check the status of the SSSD service",
        notes="Standard status check — common admin task after a config change.",
    ),
    Scenario(
        id="sssd-status-0003",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="domain logins are failing — first check if sssd is up",
        notes="Diagnostic: sssd status is the first step when domain auth breaks.",
    ),
    Scenario(
        id="sssd-status-0004",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check whether sssd is running and then show me the enrolled realms",
        notes="Multi-step: status then realm_list to assess the full auth picture.",
    ),
    Scenario(
        id="sssd-status-0005",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show the systemd status of sssd",
        notes="Direct status request naming the daemon.",
    ),
    Scenario(
        id="sssd-status-0006",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="users cannot log in with domain accounts — is sssd healthy?",
        notes="Incident triage: authentication failure mapped to sssd status.",
    ),
    Scenario(
        id="sssd-status-0007",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is the SSSD daemon active on this host?",
        notes="Boolean health inquiry about the identity services daemon.",
    ),
    Scenario(
        id="sssd-status-0008",
        tool="sssd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="sudo is failing for domain users — start by verifying sssd status",
        notes="Diagnostic: sudo failure for domain accounts often tied to sssd state.",
    ),

    # =========================================================================
    # id_lookup  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="sssd-id_lookup-0001",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="single",
        user_input="look up the identity of user jsmith",
        notes="Basic identity lookup for a domain user via sssd NSS.",
    ),
    Scenario(
        id="sssd-id_lookup-0002",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="single",
        user_input="what uid and gid does the user alice have?",
        notes="UID/GID inquiry — common when troubleshooting file permissions.",
    ),
    Scenario(
        id="sssd-id_lookup-0003",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="diagnostic",
        user_input="a domain user cannot access /data — check their identity and group membership",
        notes="Diagnostic: identity lookup to identify missing group membership.",
    ),
    Scenario(
        id="sssd-id_lookup-0004",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="single",
        user_input="show me the groups for user bob.jones",
        notes="Group membership lookup for a domain user.",
    ),
    Scenario(
        id="sssd-id_lookup-0005",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="multi",
        user_input="look up user carol and then check if sssd is caching her correctly",
        notes="Multi-step: id lookup then assess cache state.",
    ),
    Scenario(
        id="sssd-id_lookup-0006",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="single",
        user_input="what is the uid of svcaccount?",
        notes="Service account identity lookup.",
    ),
    Scenario(
        id="sssd-id_lookup-0007",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="diagnostic",
        user_input="sudo says user dan is not in the sudoers file — confirm his identity and groups",
        notes="Diagnostic: verify identity and groups when sudo access is denied.",
    ),
    Scenario(
        id="sssd-id_lookup-0008",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="single",
        user_input="look up the identity of user frank@corp.example.com",
        notes="Fully-qualified domain user identity lookup.",
    ),
    Scenario(
        id="sssd-id_lookup-0009",
        tool="sssd",
        operation="id_lookup",
        permission_class=_pc("id_lookup"),
        complexity="diagnostic",
        user_input="getent is showing different uid than id — look up grace to compare",
        notes="Diagnostic: inconsistent UID resolution between NSS sources.",
    ),

    # =========================================================================
    # cache_flush  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="sssd-cache_flush-0001",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="single",
        user_input="flush the sssd cache",
        notes="WRITE: full cache flush to force re-read from the directory.",
    ),
    Scenario(
        id="sssd-cache_flush-0002",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="single",
        user_input="clear the SSSD identity cache",
        notes="WRITE: cache clear after a directory change was applied.",
    ),
    Scenario(
        id="sssd-cache_flush-0003",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="diagnostic",
        user_input="a user's group membership changed in AD but this server still shows the old groups — flush the sssd cache",
        notes="Diagnostic-triggered WRITE: stale group cache after AD change.",
    ),
    Scenario(
        id="sssd-cache_flush-0004",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="multi",
        user_input="flush the sssd cache and then look up user harry to verify the new data comes through",
        notes="Multi-step: flush then identity lookup to confirm staleness is resolved.",
    ),
    Scenario(
        id="sssd-cache_flush-0005",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="single",
        user_input="invalidate the entire sssd cache",
        notes="WRITE: complete cache invalidation via sss_cache -E.",
    ),
    Scenario(
        id="sssd-cache_flush-0006",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="diagnostic",
        user_input="users are seeing stale password failures even after a password reset — flush the sssd cache",
        notes="Diagnostic: cached credentials causing auth failures after a reset.",
    ),
    Scenario(
        id="sssd-cache_flush-0007",
        tool="sssd",
        operation="cache_flush",
        permission_class=_pc("cache_flush"),
        complexity="multi",
        user_input="flush the sssd cache and then restart sssd to pick up fresh data",
        notes="Multi-step: cache flush followed by sssd service restart.",
    ),

    # =========================================================================
    # realm_list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="sssd-realm_list-0001",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="single",
        user_input="show me the enrolled realms on this host",
        notes="Basic realm enrollment check.",
    ),
    Scenario(
        id="sssd-realm_list-0002",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="single",
        user_input="which AD domain is this server joined to?",
        notes="Domain membership inquiry via realm list.",
    ),
    Scenario(
        id="sssd-realm_list-0003",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="diagnostic",
        user_input="domain auth is broken — list the enrolled realms to see if the join is intact",
        notes="Diagnostic: verify realm enrollment when auth fails.",
    ),
    Scenario(
        id="sssd-realm_list-0004",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="single",
        user_input="list all configured realms",
        notes="Broad realm list for an audit or compliance check.",
    ),
    Scenario(
        id="sssd-realm_list-0005",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="multi",
        user_input="list enrolled realms and then show me the sssd service status",
        notes="Multi-step: realm list combined with daemon status for a full auth health snapshot.",
    ),
    Scenario(
        id="sssd-realm_list-0006",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="single",
        user_input="is this machine joined to corp.example.com?",
        notes="Specific domain enrollment check.",
    ),
    Scenario(
        id="sssd-realm_list-0007",
        tool="sssd",
        operation="realm_list",
        permission_class=_pc("realm_list"),
        complexity="diagnostic",
        user_input="after a system rebuild, check what domains this server is enrolled in",
        notes="Post-rebuild verification of realm enrollment state.",
    ),

    # =========================================================================
    # realm_join  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="sssd-realm_join-0001",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="single",
        user_input="join this server to the corp.example.com domain",
        notes="WRITE: enroll server in AD domain.",
    ),
    Scenario(
        id="sssd-realm_join-0002",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="single",
        user_input="add this host to the idm.internal domain",
        notes="WRITE: enroll host in an IdM/FreeIPA domain.",
    ),
    Scenario(
        id="sssd-realm_join-0003",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="multi",
        user_input="join this machine to ad.company.org and then verify the enrollment with realm list",
        notes="Multi-step: join then verify enrollment.",
    ),
    Scenario(
        id="sssd-realm_join-0004",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="single",
        user_input="enroll this node in the datacenter AD realm dc.infra.local",
        notes="WRITE: datacenter server AD enrollment.",
    ),
    Scenario(
        id="sssd-realm_join-0005",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="diagnostic",
        user_input="this server was re-imaged and lost its domain membership — re-join it to corp.example.com",
        notes="Diagnostic-triggered WRITE: re-enrollment after OS reinstall.",
    ),
    Scenario(
        id="sssd-realm_join-0006",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="single",
        user_input="join this host to the test.lab domain for QA purposes",
        notes="WRITE: enrollment in a test domain.",
    ),
    Scenario(
        id="sssd-realm_join-0007",
        tool="sssd",
        operation="realm_join",
        permission_class=_pc("realm_join"),
        complexity="multi",
        user_input="join corp.example.com, then flush the sssd cache, and look up user testuser to confirm domain resolution works",
        notes="Multi-step: join domain, flush cache, verify identity lookup.",
    ),

    # =========================================================================
    # realm_leave  (DESTRUCTIVE) — 10 entries
    # =========================================================================

    Scenario(
        id="sssd-realm_leave-0001",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="remove this server from the corp.example.com domain",
        notes="DESTRUCTIVE: unenroll from AD — all domain logins lost.",
    ),
    Scenario(
        id="sssd-realm_leave-0002",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="leave the idm.internal realm",
        notes="DESTRUCTIVE: leave an IdM/FreeIPA domain.",
    ),
    Scenario(
        id="sssd-realm_leave-0003",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="this server is being decommissioned — remove it from corp.example.com",
        notes="DESTRUCTIVE: domain departure as part of server decommission.",
    ),
    Scenario(
        id="sssd-realm_leave-0004",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="multi",
        user_input="leave the corp.example.com domain and then verify realm list shows nothing",
        notes="Multi-step: leave domain then confirm no realms remain.",
    ),
    Scenario(
        id="sssd-realm_leave-0005",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="diagnostic",
        user_input="this node is being transferred to a different OU — leave the current domain first",
        notes="Diagnostic-triggered DESTRUCTIVE: leave before re-joining a different domain.",
    ),
    Scenario(
        id="sssd-realm_leave-0006",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="unenroll this machine from ad.company.org",
        notes="DESTRUCTIVE: AD unenrollment — explicit decommission action.",
    ),
    Scenario(
        id="sssd-realm_leave-0007",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="take this server out of the Active Directory domain dc.infra.local",
        notes="DESTRUCTIVE: remove server from AD domain — lockout of all domain accounts.",
    ),
    Scenario(
        id="sssd-realm_leave-0008",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="multi",
        user_input="leave the test.lab domain and then join prod.corp.com instead",
        notes="Multi-step: leave one domain then join another — migration workflow.",
    ),
    Scenario(
        id="sssd-realm_leave-0009",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="diagnostic",
        user_input="the AD environment is being retired — remove all servers from corp.example.com starting with this one",
        notes="Diagnostic context: domain retirement. DESTRUCTIVE on this host.",
    ),
    Scenario(
        id="sssd-realm_leave-0010",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("realm_leave"),
        complexity="single",
        user_input="detach this node from the corp.example.com Active Directory realm",
        notes="DESTRUCTIVE: explicit detach phrasing — same effect as realm leave.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("sssd").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "sssd", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("sssd").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
