"""finetune/scenarios/users.py — Scenario corpus for the 'users' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list                  READ        — list local user accounts (cat /etc/passwd)
  info                  READ        — show one account's id/group record (id <user>)
  add                   WRITE       — create an account (useradd)
  set_shell             WRITE       — set an account's login shell (usermod -s)
  add_to_group          WRITE       — add an account to a supplementary group (usermod -aG)
  lock                  DESTRUCTIVE — lock an account so it cannot sign in (usermod -L)
  delete                DESTRUCTIVE — delete an account (userdel)
  remove_from_privgroup DESTRUCTIVE — remove an account from the privileged group (gpasswd -d)

Coverage targets
----------------
  >= 60 entries total across all 8 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE and DESTRUCTIVE scenarios are honestly labeled (permission_class from
  the live registry) so downstream traces teach the confirm-before-write and
  typed-word-confirmation gates.

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
    """Return the live permission class for a users operation."""
    return registry.get("users").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="users-list-0001",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all local user accounts on this host",
        notes="Basic READ: enumerate all accounts from /etc/passwd.",
    ),
    Scenario(
        id="users-list-0002",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list every account that exists on this system",
        notes="Synonym phrasing for account enumeration.",
    ),
    Scenario(
        id="users-list-0003",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what users are configured on this machine?",
        notes="Operator inventories accounts before a security audit.",
    ),
    Scenario(
        id="users-list-0004",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all local accounts and tell me which ones have a login shell set",
        notes="Multi-step: list accounts then filter/interpret shell field.",
    ),
    Scenario(
        id="users-list-0005",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="a login attempt from an unknown user was flagged in the audit log — list all accounts so I can check if the name exists",
        notes="Diagnostic: security incident triage using account enumeration.",
    ),
    Scenario(
        id="users-list-0006",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="dump the passwd file so I can see all accounts",
        notes="Operator directly requests /etc/passwd listing.",
    ),
    Scenario(
        id="users-list-0007",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list the accounts on this host and count how many have uid below 1000",
        notes="Multi-step: enumerate then analyse system vs. human accounts by UID range.",
    ),
    Scenario(
        id="users-list-0008",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="after the server migration I need to confirm which accounts transferred correctly — list them all",
        notes="Diagnostic: post-migration account audit.",
    ),
    Scenario(
        id="users-list-0009",
        tool="users",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="how many user accounts are on this server?",
        notes="READ: count accounts — useful for compliance reporting.",
    ),

    # =========================================================================
    # info  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="users-info-0001",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me the account details for jdoe",
        notes="Basic READ: uid/gid/groups lookup for a named account.",
    ),
    Scenario(
        id="users-info-0002",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what groups is the deploy user a member of?",
        notes="READ: group membership check for a service account.",
    ),
    Scenario(
        id="users-info-0003",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="look up the uid and gid for the postgres account",
        notes="READ: uid/gid lookup for a database system account.",
    ),
    Scenario(
        id="users-info-0004",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="show the account record for appuser and confirm whether it is in the wheel group",
        notes="Multi-step: retrieve record then check wheel membership.",
    ),
    Scenario(
        id="users-info-0005",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="a sudo command ran as svc_backup but I do not know if that account has privilege — check its groups",
        notes="Diagnostic: verify privilege level of a service account seen in audit logs.",
    ),
    Scenario(
        id="users-info-0006",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="does the nginx account exist on this host?",
        notes="READ: existence check for a web server system account.",
    ),
    Scenario(
        id="users-info-0007",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me the id record for root",
        notes="READ: inspect the root account — common sanity check.",
    ),
    Scenario(
        id="users-info-0008",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="a cron job is failing with permission denied — check what groups the cronuser account belongs to",
        notes="Diagnostic: permission failure investigation via group membership.",
    ),
    Scenario(
        id="users-info-0009",
        tool="users",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="look up the account record for alice and then tell me if she can use sudo",
        notes="Multi-step: id lookup then interpret wheel membership for sudo eligibility.",
    ),

    # =========================================================================
    # add  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="users-add-0001",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create a new user account called deploy",
        notes="WRITE: standard service account creation.",
    ),
    Scenario(
        id="users-add-0002",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="add a user named jsmith to this system",
        notes="WRITE: new human operator account.",
    ),
    Scenario(
        id="users-add-0003",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create the svc_backup account for the backup job",
        notes="WRITE: dedicated service account for a backup process.",
    ),
    Scenario(
        id="users-add-0004",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="multi",
        user_input="create a new account called apprunner and then verify it was created successfully",
        notes="Multi-step: create account then confirm with info lookup.",
    ),
    Scenario(
        id="users-add-0005",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="we need a new system account named prometheus for the monitoring exporter",
        notes="WRITE: monitoring service account creation.",
    ),
    Scenario(
        id="users-add-0006",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="multi",
        user_input="add the user asmith and then add them to the developers group",
        notes="Multi-step: create account then assign group membership.",
    ),
    Scenario(
        id="users-add-0007",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="create an account for the new junior admin — username jradmin",
        notes="WRITE: new admin account before privileges are granted separately.",
    ),
    Scenario(
        id="users-add-0008",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="diagnostic",
        user_input="the build pipeline is failing with no such user for buildbot — create that account",
        notes="Diagnostic-triggered WRITE: missing service account causing pipeline failure.",
    ),
    Scenario(
        id="users-add-0009",
        tool="users",
        operation="add",
        permission_class=_pc("add"),
        complexity="single",
        user_input="set up an account called scanner for the vulnerability scanner process",
        notes="WRITE: least-privilege service account for a security scanner.",
    ),

    # =========================================================================
    # set_shell  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="users-set_shell-0001",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="single",
        user_input="change jdoe's login shell to /bin/bash",
        notes="WRITE: standard shell assignment for a human operator account.",
    ),
    Scenario(
        id="users-set_shell-0002",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="single",
        user_input="set the shell for the deploy account to /sbin/nologin so it cannot be used interactively",
        notes="WRITE: harden a service account by disabling interactive login.",
    ),
    Scenario(
        id="users-set_shell-0003",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="single",
        user_input="change the login shell for alice to /bin/zsh",
        notes="WRITE: user shell preference change.",
    ),
    Scenario(
        id="users-set_shell-0004",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="multi",
        user_input="set the shell for svc_backup to /sbin/nologin and then confirm the change took effect",
        notes="Multi-step: set shell then verify via info lookup.",
    ),
    Scenario(
        id="users-set_shell-0005",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="diagnostic",
        user_input="the prometheus account has a bash shell but should not be able to log in interactively — fix its shell",
        notes="Diagnostic-triggered WRITE: remediate an incorrectly configured service account shell.",
    ),
    Scenario(
        id="users-set_shell-0006",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="single",
        user_input="set the shell for scanner to /bin/false to block interactive access",
        notes="WRITE: harden vulnerability scanner account shell.",
    ),
    Scenario(
        id="users-set_shell-0007",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="single",
        user_input="give jsmith a proper login shell — set it to /bin/bash",
        notes="WRITE: fix a shell that was set to /sbin/nologin by mistake for a human account.",
    ),
    Scenario(
        id="users-set_shell-0008",
        tool="users",
        operation="set_shell",
        permission_class=_pc("set_shell"),
        complexity="multi",
        user_input="disable interactive login for all service accounts: set shell to /sbin/nologin for apprunner, then for buildbot",
        notes="Multi-step: sequential shell hardening across multiple service accounts.",
    ),

    # =========================================================================
    # add_to_group  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="users-add_to_group-0001",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="add jdoe to the docker group so he can run containers",
        notes="WRITE: grant container runtime access to a developer account.",
    ),
    Scenario(
        id="users-add_to_group-0002",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="add alice to the wheel group so she can use sudo",
        notes="WRITE: grant sudo privilege via wheel group membership.",
    ),
    Scenario(
        id="users-add_to_group-0003",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="put the deploy account in the www-data group",
        notes="WRITE: grant a deploy account access to web server files.",
    ),
    Scenario(
        id="users-add_to_group-0004",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="multi",
        user_input="add jsmith to the developers group and then confirm his group membership",
        notes="Multi-step: group assignment then verification.",
    ),
    Scenario(
        id="users-add_to_group-0005",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="diagnostic",
        user_input="the build is failing with permission denied on /var/lib/docker — check if buildbot is in the docker group and add it if not",
        notes="Diagnostic-triggered WRITE: fix a permission error by adding the service account to the right group.",
    ),
    Scenario(
        id="users-add_to_group-0006",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="add asmith to the adm group so she can read system logs",
        notes="WRITE: grant log-reading access via adm group membership.",
    ),
    Scenario(
        id="users-add_to_group-0007",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="put the prometheus account in the systemd-journal group so it can read journal entries",
        notes="WRITE: grant monitoring account access to systemd journal.",
    ),
    Scenario(
        id="users-add_to_group-0008",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="multi",
        user_input="add jradmin to the wheel group and then verify the change took effect",
        notes="Multi-step: privilege grant then confirmation — security-sensitive path.",
    ),
    Scenario(
        id="users-add_to_group-0009",
        tool="users",
        operation="add_to_group",
        permission_class=_pc("add_to_group"),
        complexity="single",
        user_input="add the scanner account to the disk group so it can read raw disk devices",
        notes="WRITE: grant hardware access for a security scanning account.",
    ),

    # =========================================================================
    # lock  (DESTRUCTIVE) — 9 entries
    # =========================================================================

    Scenario(
        id="users-lock-0001",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="single",
        user_input="lock the account for jdoe — he has left the company",
        notes="DESTRUCTIVE: immediate account lockout for a departed employee.",
    ),
    Scenario(
        id="users-lock-0002",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="single",
        user_input="lock the tempuser account",
        notes="DESTRUCTIVE: lock a temporary account after its task is complete.",
    ),
    Scenario(
        id="users-lock-0003",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="single",
        user_input="disable login for the oldadmin account immediately",
        notes="DESTRUCTIVE: lock a stale admin account as a security measure.",
    ),
    Scenario(
        id="users-lock-0004",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="multi",
        user_input="lock the testuser account and then verify it is locked",
        notes="Multi-step: lock then confirm the account cannot sign in.",
    ),
    Scenario(
        id="users-lock-0005",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="diagnostic",
        user_input="the security team detected a compromised credential for jsmith — lock that account right now",
        notes="Diagnostic-triggered DESTRUCTIVE: incident response account lockout.",
    ),
    Scenario(
        id="users-lock-0006",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="single",
        user_input="lock alice's account while she is on extended leave",
        notes="DESTRUCTIVE: temporary lockout for an absent employee.",
    ),
    Scenario(
        id="users-lock-0007",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="diagnostic",
        user_input="there are repeated failed SSH login attempts from inside the network for the guest account — lock it",
        notes="Diagnostic-triggered DESTRUCTIVE: lock account showing brute-force signs.",
    ),
    Scenario(
        id="users-lock-0008",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="multi",
        user_input="lock the contractor01 account now that the engagement is over and confirm it is inactive",
        notes="Multi-step: lock contractor account then verify lockout state.",
    ),
    Scenario(
        id="users-lock-0009",
        tool="users",
        operation="lock",
        permission_class=_pc("lock"),
        complexity="single",
        user_input="lock the intern account — their access period has ended",
        notes="DESTRUCTIVE: standard offboarding step to disable access.",
    ),

    # =========================================================================
    # delete  (DESTRUCTIVE) — 9 entries
    # =========================================================================

    Scenario(
        id="users-delete-0001",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="single",
        user_input="delete the oldadmin account — it has been locked for 90 days and is no longer needed",
        notes="DESTRUCTIVE: permanent account removal after a lockout grace period.",
    ),
    Scenario(
        id="users-delete-0002",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="single",
        user_input="remove the tempuser account from this host",
        notes="DESTRUCTIVE: delete a temporary account created for a one-off task.",
    ),
    Scenario(
        id="users-delete-0003",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="single",
        user_input="delete the contractor01 account — the engagement ended last month",
        notes="DESTRUCTIVE: post-engagement contractor account cleanup.",
    ),
    Scenario(
        id="users-delete-0004",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="multi",
        user_input="delete the test_deploy account and then confirm it no longer exists",
        notes="Multi-step: delete account then verify removal via info lookup.",
    ),
    Scenario(
        id="users-delete-0005",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="diagnostic",
        user_input="the compliance audit found a stale account 'scanold' that should have been removed months ago — delete it",
        notes="Diagnostic-triggered DESTRUCTIVE: audit-driven account cleanup.",
    ),
    Scenario(
        id="users-delete-0006",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="single",
        user_input="remove the jdoe account — he left six months ago and it was locked at that time",
        notes="DESTRUCTIVE: permanent removal of a previously locked departed-employee account.",
    ),
    Scenario(
        id="users-delete-0007",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="single",
        user_input="delete the test123 account — it was only created for a demo",
        notes="DESTRUCTIVE: clean up a demo account after use.",
    ),
    Scenario(
        id="users-delete-0008",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="multi",
        user_input="delete the svc_old account and then list all accounts to confirm it is gone",
        notes="Multi-step: delete then enumerate to confirm absence.",
    ),
    Scenario(
        id="users-delete-0009",
        tool="users",
        operation="delete",
        permission_class=_pc("delete"),
        complexity="diagnostic",
        user_input="a security scanner reported an orphaned account 'legacy_app' with no running process — delete it to reduce the attack surface",
        notes="Diagnostic-triggered DESTRUCTIVE: security-hardening cleanup of an orphaned account.",
    ),

    # =========================================================================
    # remove_from_privgroup  (DESTRUCTIVE) — 9 entries
    # =========================================================================

    Scenario(
        id="users-remove_from_privgroup-0001",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="single",
        user_input="remove jdoe from the wheel group — he should not have sudo access anymore",
        notes="DESTRUCTIVE: revoke sudo privilege by removing wheel membership.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0002",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="single",
        user_input="take the intern account out of the wheel group",
        notes="DESTRUCTIVE: privilege reduction for an intern account.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0003",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="single",
        user_input="strip sudo access from the contractor01 account",
        notes="DESTRUCTIVE: revoke privileged access at end of an engagement.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0004",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="multi",
        user_input="remove alice from the wheel group and then confirm she is no longer a member",
        notes="Multi-step: privilege revocation then group membership verification.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0005",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="diagnostic",
        user_input="the security audit found that the deploy service account is in the wheel group — that is wrong, remove it",
        notes="Diagnostic-triggered DESTRUCTIVE: remediate an over-privileged service account found in audit.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0006",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="single",
        user_input="revoke sudo rights from jsmith — he moved to a role that does not require system access",
        notes="DESTRUCTIVE: role-change-driven privilege revocation.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0007",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="diagnostic",
        user_input="a sudo command ran as appuser which should not have privilege — check its groups and remove it from wheel if present",
        notes="Diagnostic-triggered DESTRUCTIVE: investigate and remediate unexpected privileged execution.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0008",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="multi",
        user_input="remove oldadmin from wheel, then lock the account, then verify both changes",
        notes="Multi-step: privilege revocation followed by lockout — full decommission sequence.",
    ),
    Scenario(
        id="users-remove_from_privgroup-0009",
        tool="users",
        operation="remove_from_privgroup",
        permission_class=_pc("remove_from_privgroup"),
        complexity="single",
        user_input="the junior admin jradmin should no longer have unrestricted sudo — remove him from wheel",
        notes="DESTRUCTIVE: least-privilege enforcement by stripping wheel group membership.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("users").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "users", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("users").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 60, f"Need >= 60 scenarios, got {len(SCENARIOS)}"
