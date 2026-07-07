"""finetune/scenarios/pam.py — Scenario corpus for the 'pam' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  pamd_audit       READ   — display a PAM service config from /etc/pam.d/
  faillock_status  READ   — show authentication failure tallies
  faillock_reset   WRITE  — reset faillock tallies for a user or all users
  pam_auth_update  WRITE  — enable/disable a PAM profile via pam-auth-update

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled so downstream traces teach the
  confirm-before-write gate.

INV-schema-sync: permission_class for each entry is derived from the LIVE
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
    """Return the live permission class for a pam operation."""
    return registry.get("pam").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # pamd_audit  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="pam-pamd_audit-0001",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="show me the PAM config for sshd",
        notes="Basic audit of the sshd PAM service configuration.",
    ),
    Scenario(
        id="pam-pamd_audit-0002",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="what does the PAM configuration for sudo look like?",
        notes="Inspect sudo PAM config — useful when sudo auth is failing.",
    ),
    Scenario(
        id="pam-pamd_audit-0003",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="display the PAM rules for the login service",
        notes="Inspect interactive login PAM stack.",
    ),
    Scenario(
        id="pam-pamd_audit-0004",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="check the /etc/pam.d/system-auth file",
        notes="Audit the shared system-auth stack referenced by most services.",
    ),
    Scenario(
        id="pam-pamd_audit-0005",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="read the PAM config for password-auth",
        notes="Inspect the shared password-auth stack.",
    ),
    Scenario(
        id="pam-pamd_audit-0006",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="show me what pam.d says for the crond service",
        notes="Cron daemon PAM configuration — relevant when cron jobs are failing auth.",
    ),
    Scenario(
        id="pam-pamd_audit-0007",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="multi",
        user_input="show the PAM config for sshd and then explain which modules handle account lockout",
        notes="Multi-step: retrieve config then interpret faillock/pam_tally2 entries.",
    ),
    Scenario(
        id="pam-pamd_audit-0008",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="diagnostic",
        user_input="users can log in via console but not SSH — show me the sshd PAM config so we can compare it with login",
        notes="Diagnostic: compare sshd vs login PAM stacks to find the divergence.",
    ),
    Scenario(
        id="pam-pamd_audit-0009",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="diagnostic",
        user_input="sudo is failing with authentication errors — read the sudo PAM config",
        notes="Diagnostic: inspect sudo PAM config when privilege escalation fails.",
    ),
    Scenario(
        id="pam-pamd_audit-0010",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="single",
        user_input="display the PAM rules for the su command",
        notes="Inspect su PAM configuration.",
    ),
    Scenario(
        id="pam-pamd_audit-0011",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="multi",
        user_input="check the PAM config for sshd and confirm that pam_faillock is in the auth stack",
        notes="Multi-step: audit config then verify a specific module is present.",
    ),
    Scenario(
        id="pam-pamd_audit-0012",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pamd_audit"),
        complexity="diagnostic",
        user_input="after the OS update PAM auth is broken — start by reading /etc/pam.d/sshd to see if anything changed",
        notes="Diagnostic: post-update PAM audit to identify configuration drift.",
    ),

    # =========================================================================
    # faillock_status  (READ) — 11 entries
    # =========================================================================

    Scenario(
        id="pam-faillock_status-0001",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="show faillock status for all users",
        notes="Global faillock tally check — identifies locked-out accounts.",
    ),
    Scenario(
        id="pam-faillock_status-0002",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="check faillock status for user alice",
        notes="Per-user faillock tally — alice may be locked out.",
    ),
    Scenario(
        id="pam-faillock_status-0003",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="is bob locked out? check his faillock entries",
        notes="Per-user faillock check for user bob.",
    ),
    Scenario(
        id="pam-faillock_status-0004",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="how many failed login attempts are recorded for the deploy user?",
        notes="Check faillock tallies for a service account.",
    ),
    Scenario(
        id="pam-faillock_status-0005",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="diagnostic",
        user_input="a user says they cannot log in — check their faillock status before resetting anything",
        notes="Diagnostic: inspect tally before deciding whether a reset is needed.",
    ),
    Scenario(
        id="pam-faillock_status-0006",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="multi",
        user_input="show faillock status for all users and list any accounts that have recent failures",
        notes="Multi-step: show tallies then filter for accounts with recent failure entries.",
    ),
    Scenario(
        id="pam-faillock_status-0007",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="check faillock status for the root account",
        notes="Verify root account is not recording repeated failures.",
    ),
    Scenario(
        id="pam-faillock_status-0008",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="diagnostic",
        user_input="we are seeing brute-force alerts — pull faillock status for all users to see which accounts are targeted",
        notes="Diagnostic: security incident review of failed login tallies.",
    ),
    Scenario(
        id="pam-faillock_status-0009",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="single",
        user_input="show me the faillock records for the svc_backup account",
        notes="Service account faillock check during a backup authentication investigation.",
    ),
    Scenario(
        id="pam-faillock_status-0010",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="multi",
        user_input="check faillock status for user carol and then decide if a reset is warranted",
        notes="Multi-step: read tally then recommend or perform a reset.",
    ),
    Scenario(
        id="pam-faillock_status-0011",
        tool="pam",
        operation="faillock_status",
        permission_class=_pc("faillock_status"),
        complexity="diagnostic",
        user_input="the monitoring system reports repeated SSH auth failures from 10.0.1.5 — show faillock status to identify the targeted account",
        notes="Diagnostic: correlate network-level auth alerts with per-account PAM tallies.",
    ),

    # =========================================================================
    # faillock_reset  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="pam-faillock_reset-0001",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="reset the faillock counter for user alice",
        notes="WRITE: unlock alice's account by resetting the failure tally.",
    ),
    Scenario(
        id="pam-faillock_reset-0002",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="clear the faillock entries for bob so he can log in again",
        notes="WRITE: reset tally to restore login access for bob.",
    ),
    Scenario(
        id="pam-faillock_reset-0003",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="reset all faillock counters on this host",
        notes="WRITE: clear all tallies — use with caution on production hosts.",
    ),
    Scenario(
        id="pam-faillock_reset-0004",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="multi",
        user_input="check faillock status for the deploy user and then reset it if they are locked out",
        notes="Multi-step: status check then conditional WRITE reset.",
    ),
    Scenario(
        id="pam-faillock_reset-0005",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="diagnostic",
        user_input="the CI pipeline is failing auth — the deploy account is probably locked; reset its faillock counter",
        notes="Diagnostic-triggered WRITE: restore CI service account access.",
    ),
    Scenario(
        id="pam-faillock_reset-0006",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="unlock root by resetting its faillock tally",
        notes="WRITE: reset root account faillock — requires elevated privileges.",
    ),
    Scenario(
        id="pam-faillock_reset-0007",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="clear the failed-login counters for carol",
        notes="WRITE: reset PAM failure tally for user carol.",
    ),
    Scenario(
        id="pam-faillock_reset-0008",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="multi",
        user_input="reset faillock for the svc_backup user and then verify the tallies are cleared",
        notes="Multi-step: WRITE reset then READ status verification.",
    ),
    Scenario(
        id="pam-faillock_reset-0009",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="diagnostic",
        user_input="after the brute-force attempt we mitigated the source IP — now reset faillock for the targeted accounts so they can log back in",
        notes="Diagnostic-triggered WRITE: post-incident account restoration.",
    ),
    Scenario(
        id="pam-faillock_reset-0010",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("faillock_reset"),
        complexity="single",
        user_input="reset the faillock tally for user david",
        notes="WRITE: standard account-unlock operation via faillock reset.",
    ),

    # =========================================================================
    # pam_auth_update  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="pam-pam_auth_update-0001",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="enable the mkhomedir PAM profile so home directories are created on first login",
        notes="WRITE: enable mkhomedir — common post-install step for SSSD/LDAP environments.",
    ),
    Scenario(
        id="pam-pam_auth_update-0002",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="enable the pwquality profile to enforce password complexity",
        notes="WRITE: enable password quality enforcement across all PAM services.",
    ),
    Scenario(
        id="pam-pam_auth_update-0003",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="enable the faillock PAM profile",
        notes="WRITE: enable account lockout via pam_faillock across all services.",
    ),
    Scenario(
        id="pam-pam_auth_update-0004",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="disable the oddjob-mkhomedir profile",
        notes="WRITE: disable mkhomedir profile — e.g. when switching to manual provisioning.",
    ),
    Scenario(
        id="pam-pam_auth_update-0005",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="multi",
        user_input="enable mkhomedir via pam-auth-update and then confirm SSH login still works",
        notes="Multi-step: WRITE profile apply then verify login is not broken.",
    ),
    Scenario(
        id="pam-pam_auth_update-0006",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="diagnostic",
        user_input="home directories are not being created for new LDAP users — enable mkhomedir via pam-auth-update",
        notes="Diagnostic-triggered WRITE: fix missing homedir creation for directory-service accounts.",
    ),
    Scenario(
        id="pam-pam_auth_update-0007",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="apply the sss PAM profile to enable SSSD authentication",
        notes="WRITE: enable the SSSD PAM profile for directory-service integration.",
    ),
    Scenario(
        id="pam-pam_auth_update-0008",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="disable the pwquality profile — we are managing policy via a different mechanism",
        notes="WRITE: disable password quality enforcement when an external policy engine is in use.",
    ),
    Scenario(
        id="pam-pam_auth_update-0009",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="multi",
        user_input="enable the faillock profile and then check the sshd PAM config to confirm it is in the auth stack",
        notes="Multi-step: enable profile then audit the resulting config.",
    ),
    Scenario(
        id="pam-pam_auth_update-0010",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="diagnostic",
        user_input="after a security scan flagged missing account lockout controls — enable pam_faillock via pam-auth-update",
        notes="Diagnostic-triggered WRITE: remediate a compliance finding by enabling faillock.",
    ),
    Scenario(
        id="pam-pam_auth_update-0011",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="single",
        user_input="enable the krb5 PAM profile for Kerberos authentication",
        notes="WRITE: enable Kerberos PAM profile — used in Active Directory-joined hosts.",
    ),
    Scenario(
        id="pam-pam_auth_update-0012",
        tool="pam",
        operation="pam_auth_update",
        permission_class=_pc("pam_auth_update"),
        complexity="diagnostic",
        user_input="logins broke after the last PAM update — disable the new profile that was applied and revert to working state",
        notes="Diagnostic-triggered WRITE: emergency revert of a broken PAM profile.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("pam").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "pam", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("pam").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
