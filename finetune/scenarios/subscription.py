"""finetune/scenarios/subscription.py — Scenario corpus for the 'subscription' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status        READ        — show current subscription status
  list          READ        — list consumed or available subscriptions
  register      WRITE       — register this system with a subscription server
  unregister    DESTRUCTIVE — remove all entitlements and unregister
  repos_enable  WRITE       — enable a content repository
  repos_disable WRITE       — disable a content repository

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the require-typed-word gate.

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
    """Return the live permission class for a subscription operation."""
    return registry.get("subscription").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="subscription-status-0001",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the subscription status of this system",
        notes="Simple health check of the subscription state.",
    ),
    Scenario(
        id="subscription-status-0002",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is this server registered with Red Hat?",
        notes="Quick registration check before running updates.",
    ),
    Scenario(
        id="subscription-status-0003",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="dnf is throwing a 'This system is not registered' error — check the subscription status",
        notes="Diagnostic: confirm registration state when dnf fails.",
    ),
    Scenario(
        id="subscription-status-0004",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check if our Red Hat subscription is still current",
        notes="Pre-maintenance check to ensure repos will be accessible.",
    ),
    Scenario(
        id="subscription-status-0005",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check subscription status and then list what repos are enabled",
        notes="Multi-step: status followed by repo listing.",
    ),
    Scenario(
        id="subscription-status-0006",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="security updates are failing — is the subscription still valid?",
        notes="Diagnostic: subscription expiry as root cause of update failures.",
    ),
    Scenario(
        id="subscription-status-0007",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="run subscription-manager status on this host",
        notes="Direct admin invocation phrasing.",
    ),
    Scenario(
        id="subscription-status-0008",
        tool="subscription",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the system was just rebuilt — confirm it has a valid subscription before we proceed",
        notes="Post-rebuild validation of subscription state.",
    ),

    # =========================================================================
    # list  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="subscription-list-0001",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the subscriptions attached to this system",
        notes="Default consumed list — most common admin check.",
    ),
    Scenario(
        id="subscription-list-0002",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me which subscriptions this server is consuming",
        notes="Consumed subscription audit.",
    ),
    Scenario(
        id="subscription-list-0003",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what subscriptions are available to attach to this system?",
        notes="Available subscription check to find pools for attachment.",
    ),
    Scenario(
        id="subscription-list-0004",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="we think the subscription expired — list what's currently consumed",
        notes="Diagnostic: check consumed subscriptions for expiry.",
    ),
    Scenario(
        id="subscription-list-0005",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list available subscriptions and then register this host to one",
        notes="Multi-step: discover available pools then register.",
    ),
    Scenario(
        id="subscription-list-0006",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show available subscription pools for this machine",
        notes="Available pool listing for new host onboarding.",
    ),
    Scenario(
        id="subscription-list-0007",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I cannot enable the appstream repo — check what subscriptions are attached",
        notes="Diagnostic: missing entitlement investigation via list.",
    ),
    Scenario(
        id="subscription-list-0008",
        tool="subscription",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list consumed Red Hat subscriptions on this node",
        notes="Pre-decommission subscription inventory.",
    ),

    # =========================================================================
    # register  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="subscription-register-0001",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="single",
        user_input="register this server with our Red Hat account",
        notes="WRITE: initial registration of a newly provisioned host.",
    ),
    Scenario(
        id="subscription-register-0002",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="single",
        user_input="register this system using our activation key",
        notes="WRITE: activation-key-based registration — common in automated provisioning.",
    ),
    Scenario(
        id="subscription-register-0003",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="multi",
        user_input="register the host and then enable the baseos and appstream repos",
        notes="Multi-step: register followed by repo enablement.",
    ),
    Scenario(
        id="subscription-register-0004",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="diagnostic",
        user_input="dnf updates are failing because the system is not registered — register it now",
        notes="Diagnostic-triggered WRITE: registration as remediation.",
    ),
    Scenario(
        id="subscription-register-0005",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="single",
        user_input="this is a fresh Rocky Linux install, register it with Red Hat",
        notes="WRITE: first-time registration on a new deployment.",
    ),
    Scenario(
        id="subscription-register-0006",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="single",
        user_input="re-register this host with the subscription server using the org activation key",
        notes="WRITE: re-registration after a migration or rebuild.",
    ),
    Scenario(
        id="subscription-register-0007",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="multi",
        user_input="register the system with Red Hat and check the subscription status afterwards",
        notes="Multi-step: register then confirm status.",
    ),
    Scenario(
        id="subscription-register-0008",
        tool="subscription",
        operation="register",
        permission_class=_pc("register"),
        complexity="diagnostic",
        user_input="we just rebuilt this data center node — register it before the patching window opens",
        notes="Diagnostic: pre-patching registration check.",
    ),

    # =========================================================================
    # unregister  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="subscription-unregister-0001",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="single",
        user_input="unregister this host from the subscription server before we decommission it",
        notes="DESTRUCTIVE: pre-decommission unregistration to release entitlement.",
    ),
    Scenario(
        id="subscription-unregister-0002",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="single",
        user_input="remove this system's Red Hat subscription registration",
        notes="DESTRUCTIVE: entitlement removal — lockout of repos after completion.",
    ),
    Scenario(
        id="subscription-unregister-0003",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="multi",
        user_input="unregister this node and then confirm it is no longer registered",
        notes="Multi-step DESTRUCTIVE: unregister then verify via status.",
    ),
    Scenario(
        id="subscription-unregister-0004",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="diagnostic",
        user_input="this system has incorrect subscription data from a failed migration — unregister it so we can re-register cleanly",
        notes="Diagnostic-triggered DESTRUCTIVE: unregister as remediation before re-register.",
    ),
    Scenario(
        id="subscription-unregister-0005",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="single",
        user_input="release the subscription for this server — it is being retired",
        notes="DESTRUCTIVE: decommission workflow step.",
    ),
    Scenario(
        id="subscription-unregister-0006",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="single",
        user_input="unregister the system from subscription-manager",
        notes="DESTRUCTIVE: direct admin invocation phrasing.",
    ),
    Scenario(
        id="subscription-unregister-0007",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("unregister"),
        complexity="multi",
        user_input="before imaging this server, unregister the subscription and list what was consumed",
        notes="Multi-step DESTRUCTIVE: inventory then unregister for reimaging workflow.",
    ),

    # =========================================================================
    # repos_enable  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="subscription-repos_enable-0001",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="single",
        user_input="enable the BaseOS repository",
        notes="WRITE: enable core OS content repo.",
    ),
    Scenario(
        id="subscription-repos_enable-0002",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="single",
        user_input="enable the AppStream repo so I can install packages",
        notes="WRITE: enable application stream repo — most common post-registration step.",
    ),
    Scenario(
        id="subscription-repos_enable-0003",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="single",
        user_input="turn on the supplementary repository for this system",
        notes="WRITE: enable supplementary packages repo.",
    ),
    Scenario(
        id="subscription-repos_enable-0004",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="multi",
        user_input="enable the high-availability repo and then confirm it is listed as enabled",
        notes="Multi-step WRITE: enable repo then verify.",
    ),
    Scenario(
        id="subscription-repos_enable-0005",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="diagnostic",
        user_input="dnf cannot find pacemaker — enable the HighAvailability repo",
        notes="Diagnostic-triggered WRITE: enable missing repo to fix package not found.",
    ),
    Scenario(
        id="subscription-repos_enable-0006",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="single",
        user_input="enable the optional RPMs repository",
        notes="WRITE: enable optional packages repo for broader package coverage.",
    ),
    Scenario(
        id="subscription-repos_enable-0007",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="single",
        user_input="activate the RHEL extras repository",
        notes="WRITE: enable extras repo.",
    ),
    Scenario(
        id="subscription-repos_enable-0008",
        tool="subscription",
        operation="repos_enable",
        permission_class=_pc("repos_enable"),
        complexity="multi",
        user_input="enable both the baseos and appstream repos so we can run a full system update",
        notes="Multi-step WRITE: enable two repos then run dnf update.",
    ),

    # =========================================================================
    # repos_disable  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="subscription-repos_disable-0001",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="single",
        user_input="disable the optional RPMs repository on this host",
        notes="WRITE: remove optional repo to reduce update surface.",
    ),
    Scenario(
        id="subscription-repos_disable-0002",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="single",
        user_input="turn off the beta repository so packages from it are not installed",
        notes="WRITE: disable beta/testing repo in production.",
    ),
    Scenario(
        id="subscription-repos_disable-0003",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="multi",
        user_input="disable the supplementary repo and confirm it is no longer listed as enabled",
        notes="Multi-step WRITE: disable then verify.",
    ),
    Scenario(
        id="subscription-repos_disable-0004",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="diagnostic",
        user_input="packages from an old repo are conflicting with production ones — disable that repo",
        notes="Diagnostic-triggered WRITE: disable conflicting repo.",
    ),
    Scenario(
        id="subscription-repos_disable-0005",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="single",
        user_input="disable the RHEL extras repo on this server — we do not use it",
        notes="WRITE: housekeeping — remove unused repo.",
    ),
    Scenario(
        id="subscription-repos_disable-0006",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="single",
        user_input="turn off the highavailability repo on this node that is not part of a cluster",
        notes="WRITE: disable HA repo on a standalone host — reduces attack surface.",
    ),
    Scenario(
        id="subscription-repos_disable-0007",
        tool="subscription",
        operation="repos_disable",
        permission_class=_pc("repos_disable"),
        complexity="diagnostic",
        user_input="the security team flagged this host as pulling packages from an unapproved repo — disable it",
        notes="Diagnostic WRITE: compliance-driven repo removal.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("subscription").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "subscription", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("subscription").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
