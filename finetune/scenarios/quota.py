"""finetune/scenarios/quota.py — Scenario corpus for the 'quota' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  repquota    READ   — report disk quota usage for a filesystem
  quota_user  READ   — show quota limits and usage for a specific user
  quotaon     WRITE  — enable quota enforcement on a filesystem
  quotaoff    WRITE  — disable quota enforcement on a filesystem
  quotacheck  WRITE  — scan a filesystem and rebuild quota accounting files
  edquota     WRITE  — set quota limits for a user on a filesystem

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
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
    """Return the live permission class for a quota operation."""
    return registry.get("quota").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # repquota  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="quota-repquota-0001",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="single",
        user_input="show me the quota usage report for /home",
        notes="Simple read: repquota on the home filesystem.",
    ),
    Scenario(
        id="quota-repquota-0002",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="single",
        user_input="list all users and their disk usage on /data",
        notes="Admin needs a quick overview of /data quota consumption.",
    ),
    Scenario(
        id="quota-repquota-0003",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="single",
        user_input="who is over their disk quota on this server?",
        notes="Scan all quota-enabled filesystems for users exceeding soft or hard limits.",
    ),
    Scenario(
        id="quota-repquota-0004",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="multi",
        user_input="run a quota report for /home and tell me which users are over their soft limit",
        notes="Multi-step: report then filter for over-limit users.",
    ),
    Scenario(
        id="quota-repquota-0005",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="diagnostic",
        user_input="the /home filesystem is nearly full — find out which users are consuming the most space",
        notes="Diagnostic: use repquota to triage a full filesystem.",
    ),
    Scenario(
        id="quota-repquota-0006",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="single",
        user_input="show disk quota report for the /var/mail filesystem",
        notes="Read: quota report for a mail spool filesystem.",
    ),
    Scenario(
        id="quota-repquota-0007",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="diagnostic",
        user_input="users are complaining they cannot save files — check who is at or near their disk limit",
        notes="Diagnostic: quota report as first triage step for disk write failures.",
    ),
    Scenario(
        id="quota-repquota-0008",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="multi",
        user_input="generate a quota report for /home and also check the grace times for anyone in the grace period",
        notes="Multi-step: report then check grace deadlines.",
    ),
    Scenario(
        id="quota-repquota-0009",
        tool="quota",
        operation="repquota",
        permission_class=_pc("repquota"),
        complexity="single",
        user_input="report quota usage across all filesystems",
        notes="Read: repquota -a to cover all quota-enabled filesystems at once.",
    ),

    # =========================================================================
    # quota_user  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="quota-quota_user-0001",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="single",
        user_input="what are the disk quota limits for user alice?",
        notes="Simple read: show quota for a specific user.",
    ),
    Scenario(
        id="quota-quota_user-0002",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="single",
        user_input="check how much disk space bob has used and what his limit is",
        notes="Read: quota status for a developer account.",
    ),
    Scenario(
        id="quota-quota_user-0003",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="diagnostic",
        user_input="alice says she cannot upload files — check her quota to see if she is over the limit",
        notes="Diagnostic: quota check for a user reporting disk write failures.",
    ),
    Scenario(
        id="quota-quota_user-0004",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="single",
        user_input="show the quota for the jenkins service account",
        notes="Read: quota for a build system service account.",
    ),
    Scenario(
        id="quota-quota_user-0005",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="multi",
        user_input="check charlie's quota and if he is over 80% usage tell me the hard limit",
        notes="Multi-step: check quota then compare against threshold.",
    ),
    Scenario(
        id="quota-quota_user-0006",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="single",
        user_input="how much disk space does the backup user have left?",
        notes="Read: quota check for a backup service account.",
    ),
    Scenario(
        id="quota-quota_user-0007",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="diagnostic",
        user_input="the nightly backup job failed with a disk full error — check the backup user's quota",
        notes="Diagnostic: quota check after a backup job disk failure.",
    ),
    Scenario(
        id="quota-quota_user-0008",
        tool="quota",
        operation="quota_user",
        permission_class=_pc("quota_user"),
        complexity="single",
        user_input="show disk quota info for user dave",
        notes="Read: basic quota lookup for a standard user.",
    ),

    # =========================================================================
    # quotaon  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="quota-quotaon-0001",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="single",
        user_input="enable disk quotas on /home",
        notes="WRITE: turn on quota enforcement on the home filesystem.",
    ),
    Scenario(
        id="quota-quotaon-0002",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="single",
        user_input="turn quotas on for the /data filesystem",
        notes="WRITE: enable quotas on a data filesystem.",
    ),
    Scenario(
        id="quota-quotaon-0003",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="multi",
        user_input="enable quotas on /home and then verify they are active",
        notes="Multi-step: quotaon then repquota to confirm enforcement is live.",
    ),
    Scenario(
        id="quota-quotaon-0004",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="diagnostic",
        user_input="disk limits are not being enforced on /home — turn quotas on",
        notes="Diagnostic-triggered WRITE: re-enable quotas that were accidentally turned off.",
    ),
    Scenario(
        id="quota-quotaon-0005",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="single",
        user_input="activate quota enforcement on /var/mail",
        notes="WRITE: enable quotas on a mail spool filesystem.",
    ),
    Scenario(
        id="quota-quotaon-0006",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="multi",
        user_input="run quotacheck on /home first, then enable quotas",
        notes="Multi-step: quotacheck to build accounting files, then quotaon.",
    ),
    Scenario(
        id="quota-quotaon-0007",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="single",
        user_input="enable user and group quotas on /home",
        notes="WRITE: enable both user and group quota enforcement.",
    ),
    Scenario(
        id="quota-quotaon-0008",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quotaon"),
        complexity="diagnostic",
        user_input="after the server reboot quotas are not active — re-enable them on /home",
        notes="Diagnostic: restore quota enforcement after reboot cleared the state.",
    ),

    # =========================================================================
    # quotaoff  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="quota-quotaoff-0001",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="single",
        user_input="disable disk quotas on /home",
        notes="WRITE: turn off quota enforcement on the home filesystem.",
    ),
    Scenario(
        id="quota-quotaoff-0002",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="single",
        user_input="turn off quotas on /data for the maintenance window",
        notes="WRITE: disable quotas temporarily during maintenance.",
    ),
    Scenario(
        id="quota-quotaoff-0003",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="multi",
        user_input="disable quotas on /home, then run quotacheck to rebuild the accounting files, then re-enable",
        notes="Multi-step: quotaoff, quotacheck, quotaon cycle for maintenance.",
    ),
    Scenario(
        id="quota-quotaoff-0004",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="diagnostic",
        user_input="quota enforcement is causing performance issues on /home — turn it off while we investigate",
        notes="Diagnostic-triggered WRITE: disable quotas to isolate a performance issue.",
    ),
    Scenario(
        id="quota-quotaoff-0005",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="single",
        user_input="disable quota enforcement on /var/mail",
        notes="WRITE: turn off quotas on the mail spool filesystem.",
    ),
    Scenario(
        id="quota-quotaoff-0006",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="single",
        user_input="turn off disk quotas on /scratch — that filesystem is being decommissioned",
        notes="WRITE: disable quotas before decommissioning a filesystem.",
    ),
    Scenario(
        id="quota-quotaoff-0007",
        tool="quota",
        operation="quotaoff",
        permission_class=_pc("quotaoff"),
        complexity="multi",
        user_input="turn off quotas on /home and confirm the report no longer shows enforcement",
        notes="Multi-step: quotaoff then verify with repquota.",
    ),

    # =========================================================================
    # quotacheck  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="quota-quotacheck-0001",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="single",
        user_input="run quotacheck on /home to rebuild the quota database",
        notes="WRITE: rebuild quota accounting files on the home filesystem.",
    ),
    Scenario(
        id="quota-quotacheck-0002",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="single",
        user_input="scan /home and update the quota accounting files",
        notes="WRITE: quotacheck scan after files were added without quota enforcement.",
    ),
    Scenario(
        id="quota-quotacheck-0003",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="multi",
        user_input="disable quotas on /home, run quotacheck, then re-enable quotas",
        notes="Multi-step: safe quotacheck cycle (off -> check -> on).",
    ),
    Scenario(
        id="quota-quotacheck-0004",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="diagnostic",
        user_input="the quota report shows wildly incorrect values — rebuild the quota database for /home",
        notes="Diagnostic-triggered WRITE: quotacheck to fix corrupted accounting files.",
    ),
    Scenario(
        id="quota-quotacheck-0005",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="single",
        user_input="initialise quota tracking on /data — there are no quota files yet",
        notes="WRITE: first-time quotacheck to create aquota.user and aquota.group.",
    ),
    Scenario(
        id="quota-quotacheck-0006",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="diagnostic",
        user_input="after the unclean shutdown the quota files on /home may be inconsistent — check and repair them",
        notes="Diagnostic: run quotacheck after an unclean filesystem unmount.",
    ),
    Scenario(
        id="quota-quotacheck-0007",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="single",
        user_input="check quota consistency on /var/mail",
        notes="WRITE: quotacheck on the mail spool filesystem.",
    ),
    Scenario(
        id="quota-quotacheck-0008",
        tool="quota",
        operation="quotacheck",
        permission_class=_pc("quotacheck"),
        complexity="multi",
        user_input="rebuild the quota database for /home and then report current usage",
        notes="Multi-step: quotacheck to rebuild, then repquota to confirm fresh numbers.",
    ),

    # =========================================================================
    # edquota  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="quota-edquota-0001",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="set a 500MB soft limit and 600MB hard limit for user alice on /home",
        notes="WRITE: assign block quota limits to a user.",
    ),
    Scenario(
        id="quota-edquota-0002",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="give user bob a 1GB hard disk limit on /home",
        notes="WRITE: set a hard block limit for a developer account.",
    ),
    Scenario(
        id="quota-edquota-0003",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="remove disk limits for the jenkins service account on /home",
        notes="WRITE: set limits to 0 (no limit) for a build service account.",
    ),
    Scenario(
        id="quota-edquota-0004",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="multi",
        user_input="set a 2GB hard limit for user charlie on /home and then check his current usage",
        notes="Multi-step: set limits then confirm with quota_user.",
    ),
    Scenario(
        id="quota-edquota-0005",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="diagnostic",
        user_input="charlie is in a grace-period breach — reduce his hard limit to match his current usage to force cleanup",
        notes="Diagnostic-triggered WRITE: tighten quota to force a user to free space.",
    ),
    Scenario(
        id="quota-edquota-0006",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="set a 10000 inode limit for user alice on /home",
        notes="WRITE: set an inode (file count) limit rather than a block limit.",
    ),
    Scenario(
        id="quota-edquota-0007",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="increase alice's disk quota from 500MB to 1GB on /home — she needs more space",
        notes="WRITE: expand a user's quota limit.",
    ),
    Scenario(
        id="quota-edquota-0008",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="single",
        user_input="set a 5GB soft limit and 6GB hard limit for the backup service account on /data",
        notes="WRITE: quota limits for a backup service account on a data filesystem.",
    ),
    Scenario(
        id="quota-edquota-0009",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="multi",
        user_input="set 512MB hard limits for users alice, bob, and charlie on /home",
        notes="Multi-step: edquota called for each user to apply a standard limit policy.",
    ),
    Scenario(
        id="quota-edquota-0010",
        tool="quota",
        operation="edquota",
        permission_class=_pc("edquota"),
        complexity="diagnostic",
        user_input="the disk is filling up — set a 200MB hard limit for every user that currently has no limit on /home",
        notes="Diagnostic: emergency quota enforcement to cap unconstrained users.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("quota").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "quota", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("quota").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
