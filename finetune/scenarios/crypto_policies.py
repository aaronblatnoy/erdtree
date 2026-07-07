"""finetune/scenarios/crypto_policies.py — Scenario corpus for the 'crypto_policies' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  get          READ   — show the currently active crypto policy
  list         READ   — list all available crypto policy names
  set          WRITE  — apply a named crypto policy system-wide
  fips-status  READ   — report whether FIPS 140 mode is enabled
  fips-enable  WRITE  — enable FIPS 140 mode (reboot required)

Coverage targets
----------------
  >= 40 entries total across all 5 operations.
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
    """Return the live permission class for a crypto_policies operation."""
    return registry.get("crypto_policies").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # get  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="crypto_policies-get-0001",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="what crypto policy is this system using?",
        notes="Basic query: show the active system-wide crypto policy.",
    ),
    Scenario(
        id="crypto_policies-get-0002",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="show me the current cryptographic policy",
        notes="Synonym phrasing for get current policy.",
    ),
    Scenario(
        id="crypto_policies-get-0003",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="is the system running the DEFAULT or FUTURE crypto policy?",
        notes="Operator wants to confirm the active policy before making a decision.",
    ),
    Scenario(
        id="crypto_policies-get-0004",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="diagnostic",
        user_input="TLS 1.0 connections are being rejected — what crypto policy is active on this host?",
        notes="Diagnostic: correlate TLS version rejection with policy setting.",
    ),
    Scenario(
        id="crypto_policies-get-0005",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="diagnostic",
        user_input="the compliance scan says we need FIPS-level crypto — check what policy is currently applied",
        notes="Diagnostic: audit finding triggers a policy read.",
    ),
    Scenario(
        id="crypto_policies-get-0006",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="multi",
        user_input="show the current crypto policy and then list all available options",
        notes="Multi-step: get current then list alternatives.",
    ),
    Scenario(
        id="crypto_policies-get-0007",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="print the active crypto policy on this box",
        notes="Simple single-step inspection.",
    ),
    Scenario(
        id="crypto_policies-get-0008",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="diagnostic",
        user_input="ssh is refusing old ciphers — start by checking what crypto policy is configured",
        notes="Diagnostic entry point: policy check before deciding on remediation.",
    ),
    Scenario(
        id="crypto_policies-get-0009",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="multi",
        user_input="read the current policy, and if it is LEGACY warn me that this weakens security",
        notes="Multi-step: read then conditionally advise.",
    ),
    Scenario(
        id="crypto_policies-get-0010",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="what is the value returned by update-crypto-policies --show?",
        notes="Technical phrasing referencing the binary directly.",
    ),

    # =========================================================================
    # list  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="crypto_policies-list-0001",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what crypto policies are available on this system?",
        notes="List all policy names for awareness.",
    ),
    Scenario(
        id="crypto_policies-list-0002",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all the crypto policy options I can choose from",
        notes="Operator exploring before committing to a policy change.",
    ),
    Scenario(
        id="crypto_policies-list-0003",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list the available policies and tell me which one is the most secure",
        notes="Multi-step: list then advise on best choice.",
    ),
    Scenario(
        id="crypto_policies-list-0004",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="is FUTURE a valid crypto policy name?",
        notes="Operator checking if a specific policy name is supported.",
    ),
    Scenario(
        id="crypto_policies-list-0005",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="print all available cryptographic policy names",
        notes="Synonym phrasing for list.",
    ),
    Scenario(
        id="crypto_policies-list-0006",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all policies and then show me which one is currently active",
        notes="Multi-step: list then get.",
    ),
    Scenario(
        id="crypto_policies-list-0007",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I need to upgrade to a stronger crypto setting — list what is available first",
        notes="Diagnostic-driven: list policies before choosing a stronger one.",
    ),
    Scenario(
        id="crypto_policies-list-0008",
        tool="crypto_policies",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what policy options does update-crypto-policies support?",
        notes="Technical phrasing referencing the binary.",
    ),

    # =========================================================================
    # set  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="crypto_policies-set-0001",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set the crypto policy to DEFAULT",
        notes="WRITE: restore to the default policy.",
    ),
    Scenario(
        id="crypto_policies-set-0002",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="switch the system to the FUTURE crypto policy",
        notes="WRITE: apply the stricter FUTURE policy.",
    ),
    Scenario(
        id="crypto_policies-set-0003",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set the crypto policy to LEGACY so that older clients can connect",
        notes="WRITE: weaken policy for compatibility — operator is aware of implications.",
    ),
    Scenario(
        id="crypto_policies-set-0004",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="multi",
        user_input="set the crypto policy to FUTURE and then confirm the change took effect",
        notes="Multi-step: apply then verify with get.",
    ),
    Scenario(
        id="crypto_policies-set-0005",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="the security audit requires FUTURE-grade crypto — apply it now",
        notes="Diagnostic-triggered WRITE: audit finding drives policy upgrade.",
    ),
    Scenario(
        id="crypto_policies-set-0006",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="apply the DEFAULT:NO-SHA1 policy on this host",
        notes="WRITE: apply a subpolicy variant to drop SHA1 support.",
    ),
    Scenario(
        id="crypto_policies-set-0007",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="multi",
        user_input="change the crypto policy to DEFAULT and restart sshd so it picks up the change",
        notes="Multi-step: set policy then restart dependent service.",
    ),
    Scenario(
        id="crypto_policies-set-0008",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="update the cryptographic policy to FIPS",
        notes="WRITE: set FIPS policy via update-crypto-policies (not the same as fips-mode-setup).",
    ),
    Scenario(
        id="crypto_policies-set-0009",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="applications using TLS 1.0 are breaking after the last security hardening pass — revert the crypto policy to DEFAULT",
        notes="Diagnostic rollback: compatibility issue after tightening.",
    ),
    Scenario(
        id="crypto_policies-set-0010",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="multi",
        user_input="set crypto policy to FUTURE, check which services need a restart to pick up the new ciphers, and restart them",
        notes="Multi-step: policy set followed by service restart sweep.",
    ),
    Scenario(
        id="crypto_policies-set-0011",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="run update-crypto-policies to set FIPS:NO-CAMELLIA",
        notes="WRITE: apply FIPS subpolicy excluding Camellia cipher.",
    ),
    Scenario(
        id="crypto_policies-set-0012",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="the PCI-DSS assessment failed due to weak ciphers — tighten the crypto policy to FUTURE immediately",
        notes="Diagnostic-triggered WRITE: compliance gap drives an urgent policy upgrade.",
    ),

    # =========================================================================
    # fips-status  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="crypto_policies-fips-status-0001",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="single",
        user_input="is FIPS mode enabled on this system?",
        notes="Basic FIPS status check.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0002",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="single",
        user_input="check whether this host is running in FIPS 140 mode",
        notes="Compliance check: FIPS 140 status query.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0003",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="diagnostic",
        user_input="the DoD compliance report says FIPS must be active — verify whether it is currently enabled",
        notes="Diagnostic: compliance audit triggers FIPS status check.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0004",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="single",
        user_input="run fips-mode-setup --check and tell me the result",
        notes="Technical phrasing referencing the binary.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0005",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="multi",
        user_input="check the FIPS status and if it is not enabled, tell me what steps are needed to enable it",
        notes="Multi-step: status check then conditional advice.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0006",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="single",
        user_input="is this a FIPS-compliant host?",
        notes="Operator asks about compliance posture; maps to fips-status.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0007",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="diagnostic",
        user_input="an OpenSSL error says FIPS is required but the library says it is not active — what does fips-mode-setup say?",
        notes="Diagnostic: library error triggers FIPS configuration check.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0008",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="single",
        user_input="confirm FIPS mode status before the security team's inspection",
        notes="Pre-inspection status confirmation.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0009",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="multi",
        user_input="check FIPS status on this host and compare it to the crypto policy that is currently set",
        notes="Multi-step: fips-status followed by get to compare configuration.",
    ),
    Scenario(
        id="crypto_policies-fips-status-0010",
        tool="crypto_policies",
        operation="fips-status",
        permission_class=_pc("fips-status"),
        complexity="diagnostic",
        user_input="after the last reboot the team believes FIPS mode should have engaged — verify it is active",
        notes="Diagnostic post-reboot verification of FIPS activation.",
    ),

    # =========================================================================
    # fips-enable  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="crypto_policies-fips-enable-0001",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="single",
        user_input="enable FIPS mode on this host",
        notes="WRITE: enable FIPS 140 mode system-wide.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0002",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="single",
        user_input="turn on FIPS 140 compliance mode",
        notes="WRITE: synonym phrasing for fips-enable.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0003",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="multi",
        user_input="enable FIPS mode and then confirm it has been applied",
        notes="Multi-step: enable then status check.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0004",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="diagnostic",
        user_input="the DoD security checklist requires FIPS 140 — enable it now and plan the reboot",
        notes="Diagnostic-triggered WRITE: compliance gap drives FIPS enablement.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0005",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="single",
        user_input="run fips-mode-setup --enable on this system",
        notes="WRITE: technical phrasing referencing the binary directly.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0006",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="multi",
        user_input="enable FIPS mode and remind me that a reboot is required before it takes effect",
        notes="Multi-step: enable then advise on reboot requirement.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0007",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="single",
        user_input="put this server into FIPS 140-2 mode",
        notes="WRITE: operator uses the standard version designation.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0008",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="diagnostic",
        user_input="the audit found this host is missing FIPS mode — enable it and schedule a maintenance window reboot",
        notes="Diagnostic-triggered WRITE: enable FIPS and note the required reboot.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0009",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="multi",
        user_input="check the current FIPS status; if it is off, enable it",
        notes="Multi-step: conditional enable based on prior status check.",
    ),
    Scenario(
        id="crypto_policies-fips-enable-0010",
        tool="crypto_policies",
        operation="fips-enable",
        permission_class=_pc("fips-enable"),
        complexity="diagnostic",
        user_input="NSS library errors suggest FIPS is required but not active — enable it",
        notes="Diagnostic: library-level error drives FIPS enablement.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("crypto_policies").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "crypto_policies", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("crypto_policies").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
