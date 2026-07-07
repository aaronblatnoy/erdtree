"""finetune/scenarios/samba.py — Scenario corpus for the 'samba' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  smbd_status      READ        — show status of smbd and nmbd daemons
  nmbd_status      READ        — show status of nmbd daemon
  testparm         READ        — validate smb.conf configuration
  smbpasswd_add    WRITE       — add a user to the Samba user database
  smbpasswd_delete DESTRUCTIVE — remove a user from the Samba user database
  usershare_list   READ        — list all usershares
  usershare_add    WRITE       — add or update a usershare

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.

INV-schema-sync: permission_class derived LIVE from registry, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass — local copy, field names match the canonical shape
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
    """Return the live permission class for a samba operation."""
    return registry.get("samba").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # smbd_status  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="samba-smbd_status-0001",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="single",
        user_input="is Samba running?",
        notes="Simple health check on smbd and nmbd.",
    ),
    Scenario(
        id="samba-smbd_status-0002",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="single",
        user_input="show me the status of the smbd and nmbd services",
        notes="Explicit status request for both Samba daemons.",
    ),
    Scenario(
        id="samba-smbd_status-0003",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="diagnostic",
        user_input="users can't connect to the file share — is smbd up?",
        notes="Diagnostic: check Samba daemon status as first step in a connectivity failure.",
    ),
    Scenario(
        id="samba-smbd_status-0004",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="multi",
        user_input="check if Samba is running and tell me how long it has been up",
        notes="Multi-step: status then parse uptime from output.",
    ),
    Scenario(
        id="samba-smbd_status-0005",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="single",
        user_input="confirm the Samba file server is active on this host",
        notes="Basic confirmation check before a maintenance window.",
    ),
    Scenario(
        id="samba-smbd_status-0006",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="diagnostic",
        user_input="the Windows clients say they cannot find the server — check if smbd is running",
        notes="Diagnostic: SMB discovery issue — verify daemon state.",
    ),
    Scenario(
        id="samba-smbd_status-0007",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("smbd_status"),
        complexity="single",
        user_input="are both smbd and nmbd services active?",
        notes="Explicit dual-daemon status check.",
    ),

    # =========================================================================
    # nmbd_status  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="samba-nmbd_status-0001",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="single",
        user_input="is nmbd running?",
        notes="Check NetBIOS name daemon status.",
    ),
    Scenario(
        id="samba-nmbd_status-0002",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="diagnostic",
        user_input="Windows machines can't see this server in Network Neighborhood — check nmbd",
        notes="Diagnostic: NetBIOS browse list issue — check nmbd.",
    ),
    Scenario(
        id="samba-nmbd_status-0003",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="single",
        user_input="show the nmbd service status",
        notes="Direct nmbd status request.",
    ),
    Scenario(
        id="samba-nmbd_status-0004",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="multi",
        user_input="check nmbd status and let me know if it needs to be restarted",
        notes="Multi-step: status check followed by remediation recommendation.",
    ),
    Scenario(
        id="samba-nmbd_status-0005",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="diagnostic",
        user_input="NetBIOS name resolution seems broken — verify nmbd is up",
        notes="Diagnostic: NetBIOS resolution failure — verify daemon health.",
    ),
    Scenario(
        id="samba-nmbd_status-0006",
        tool="samba",
        operation="nmbd_status",
        permission_class=_pc("nmbd_status"),
        complexity="single",
        user_input="what is the current state of the nmbd daemon?",
        notes="General nmbd daemon health query.",
    ),

    # =========================================================================
    # testparm  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="samba-testparm-0001",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="single",
        user_input="validate the Samba configuration file",
        notes="Run testparm to verify smb.conf is syntactically valid.",
    ),
    Scenario(
        id="samba-testparm-0002",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="single",
        user_input="check smb.conf for errors",
        notes="Direct config validation request.",
    ),
    Scenario(
        id="samba-testparm-0003",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="multi",
        user_input="I just edited smb.conf — check it for errors and show me the parsed config",
        notes="Multi-step: validate config then review parsed output.",
    ),
    Scenario(
        id="samba-testparm-0004",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="diagnostic",
        user_input="Samba won't restart after my config change — run testparm to find the syntax error",
        notes="Diagnostic: identify config error preventing service restart.",
    ),
    Scenario(
        id="samba-testparm-0005",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="single",
        user_input="is the smb.conf configuration valid?",
        notes="Straightforward validity check.",
    ),
    Scenario(
        id="samba-testparm-0006",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="diagnostic",
        user_input="clients are getting errors connecting to shares — validate the Samba config",
        notes="Diagnostic: connectivity errors prompted a config check.",
    ),
    Scenario(
        id="samba-testparm-0007",
        tool="samba",
        operation="testparm",
        permission_class=_pc("testparm"),
        complexity="multi",
        user_input="run testparm and then restart Samba if the config is clean",
        notes="Multi-step: conditional restart after successful config validation.",
    ),

    # =========================================================================
    # smbpasswd_add  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="samba-smbpasswd_add-0001",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="single",
        user_input="add jsmith to the Samba user database",
        notes="WRITE: add a new user to Samba password database.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0002",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="single",
        user_input="create a Samba account for the user alice",
        notes="WRITE: provision a Samba account for an existing system user.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0003",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="multi",
        user_input="add bob to Samba and then verify he can be listed in the user database",
        notes="Multi-step: add user then confirm registration.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0004",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="single",
        user_input="give svcaccount access to the Samba shares",
        notes="WRITE: add a service account to Samba.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0005",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="diagnostic",
        user_input="the user carol can't log into the file share — make sure she has a Samba password entry",
        notes="Diagnostic-triggered WRITE: add Samba password entry to resolve access failure.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0006",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="single",
        user_input="register the user devops in the Samba database",
        notes="WRITE: onboarding a new developer account to Samba.",
    ),
    Scenario(
        id="samba-smbpasswd_add-0007",
        tool="samba",
        operation="smbpasswd_add",
        permission_class=_pc("smbpasswd_add"),
        complexity="multi",
        user_input="add the user analyst to Samba and confirm smbd is still running afterwards",
        notes="Multi-step: add user then verify Samba daemon health.",
    ),

    # =========================================================================
    # smbpasswd_delete  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="samba-smbpasswd_delete-0001",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="single",
        user_input="remove the Samba account for the departed user jsmith",
        notes="DESTRUCTIVE: delete a Samba user after employee departure.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0002",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="single",
        user_input="delete alice's Samba password entry",
        notes="DESTRUCTIVE: remove user from Samba database — locks out share access.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0003",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="multi",
        user_input="revoke Samba access for bob and then check the usershare list",
        notes="Multi-step DESTRUCTIVE: delete user then audit share configuration.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0004",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="diagnostic",
        user_input="a terminated contractor still has file share access — remove their Samba account",
        notes="Diagnostic-triggered DESTRUCTIVE: security remediation via user removal.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0005",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="single",
        user_input="delete the Samba entry for svcaccount since it is being decommissioned",
        notes="DESTRUCTIVE: remove a service account from Samba during decommission.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0006",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="single",
        user_input="remove devops from the Samba user database",
        notes="DESTRUCTIVE: offboarding a developer from share access.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-0007",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("smbpasswd_delete"),
        complexity="multi",
        user_input="delete the Samba account for tempuser and verify the deletion by checking testparm",
        notes="Multi-step DESTRUCTIVE: delete user then validate config still passes.",
    ),

    # =========================================================================
    # usershare_list  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="samba-usershare_list-0001",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="single",
        user_input="list all the Samba usershares on this server",
        notes="Inventory of current usershares.",
    ),
    Scenario(
        id="samba-usershare_list-0002",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="single",
        user_input="what shares are currently configured?",
        notes="Quick usershare audit.",
    ),
    Scenario(
        id="samba-usershare_list-0003",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="diagnostic",
        user_input="a user says they cannot see the share — list all usershares to check if it exists",
        notes="Diagnostic: verify share existence before deeper troubleshooting.",
    ),
    Scenario(
        id="samba-usershare_list-0004",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="multi",
        user_input="list the usershares and then show me testparm output to cross-check them",
        notes="Multi-step: list shares then validate against config.",
    ),
    Scenario(
        id="samba-usershare_list-0005",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="single",
        user_input="show me all the net usershares defined on this host",
        notes="Explicit net usershare list request.",
    ),
    Scenario(
        id="samba-usershare_list-0006",
        tool="samba",
        operation="usershare_list",
        permission_class=_pc("usershare_list"),
        complexity="diagnostic",
        user_input="I think someone deleted a share by accident — list all usershares to check",
        notes="Diagnostic: audit share list to detect accidental removal.",
    ),

    # =========================================================================
    # usershare_add  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="samba-usershare_add-0001",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="single",
        user_input="create a Samba share called 'data' pointing to /srv/data",
        notes="WRITE: add a new read-only usershare for a data directory.",
    ),
    Scenario(
        id="samba-usershare_add-0002",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="single",
        user_input="add a usershare named 'backups' for the /backups directory with full access",
        notes="WRITE: create a writable usershare for a backup directory.",
    ),
    Scenario(
        id="samba-usershare_add-0003",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="multi",
        user_input="add the usershare 'reports' for /srv/reports and then list all shares to confirm",
        notes="Multi-step WRITE: add share then verify with usershare list.",
    ),
    Scenario(
        id="samba-usershare_add-0004",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="single",
        user_input="share the /opt/deploy folder as a Samba usershare called 'deploy'",
        notes="WRITE: expose a deployment directory as a usershare.",
    ),
    Scenario(
        id="samba-usershare_add-0005",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="diagnostic",
        user_input="the 'media' share went missing after the reboot — re-add it pointing to /srv/media",
        notes="Diagnostic-triggered WRITE: re-create a share that disappeared.",
    ),
    Scenario(
        id="samba-usershare_add-0006",
        tool="samba",
        operation="usershare_add",
        permission_class=_pc("usershare_add"),
        complexity="multi",
        user_input="add a usershare 'scratch' for /tmp/scratch, validate the config with testparm, then check smbd status",
        notes="Multi-step WRITE: add share, validate, verify service health.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("samba").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "samba", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("samba").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
