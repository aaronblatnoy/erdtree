"""finetune/scenarios/nfs.py — Scenario corpus for the 'nfs' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  showmount        READ        — list exports advertised by a remote NFS server
  exportfs_list    READ        — list active exports on this host
  exportfs_add     WRITE       — re-read /etc/exports and publish all exports
  exportfs_unexport DESTRUCTIVE — revoke a specific NFS export (access loss)
  exports_view     READ        — display /etc/exports configuration
  nfs_start        WRITE       — start the nfs-server service
  nfs_stop         WRITE       — stop the nfs-server service
  mount_client     WRITE       — mount a remote NFS share on this host

Coverage targets
----------------
  >= 40 entries total across all 8 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the explicit-confirmation gate.

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
# Field names EXACT for Phase-13 JOIN normalisation.
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
    """Return the live permission class for an nfs operation."""
    return registry.get("nfs").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # showmount  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="nfs-showmount-0001",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="single",
        user_input="show me what NFS shares are exported by fileserver.corp.local",
        notes="Standard showmount -e to enumerate remote exports.",
    ),
    Scenario(
        id="nfs-showmount-0002",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="single",
        user_input="list the NFS exports on 192.168.1.50",
        notes="Show exports by IP address rather than hostname.",
    ),
    Scenario(
        id="nfs-showmount-0003",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="diagnostic",
        user_input="I can't mount anything from nas01 — can you check what it's actually exporting?",
        notes="Diagnostic: enumerate exports to verify availability before attempting a mount.",
    ),
    Scenario(
        id="nfs-showmount-0004",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="multi",
        user_input="check the exports on storage.internal and then mount the /backups share to /mnt/backups",
        notes="Multi-step: showmount to discover path, then mount.",
    ),
    Scenario(
        id="nfs-showmount-0005",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="single",
        user_input="what NFS directories does filer02.datacenter.net export?",
        notes="Enumerate exports from a datacenter filer.",
    ),
    Scenario(
        id="nfs-showmount-0006",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("showmount"),
        complexity="diagnostic",
        user_input="the NFS mount keeps failing — first show me what the server is actually advertising",
        notes="Diagnostic: verify the server is advertising the expected export path.",
    ),

    # =========================================================================
    # exportfs_list  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="nfs-exportfs_list-0001",
        tool="nfs",
        operation="exportfs_list",
        permission_class=_pc("exportfs_list"),
        complexity="single",
        user_input="show me the currently active NFS exports on this server",
        notes="List live exports via exportfs -v.",
    ),
    Scenario(
        id="nfs-exportfs_list-0002",
        tool="nfs",
        operation="exportfs_list",
        permission_class=_pc("exportfs_list"),
        complexity="diagnostic",
        user_input="a client says it can't see the /data share — what does the server say it's exporting right now?",
        notes="Diagnostic: compare live exports with what the client expects.",
    ),
    Scenario(
        id="nfs-exportfs_list-0003",
        tool="nfs",
        operation="exportfs_list",
        permission_class=_pc("exportfs_list"),
        complexity="multi",
        user_input="list the active exports and then show the /etc/exports file so I can compare them",
        notes="Multi-step: list live exports then view configuration for comparison.",
    ),
    Scenario(
        id="nfs-exportfs_list-0004",
        tool="nfs",
        operation="exportfs_list",
        permission_class=_pc("exportfs_list"),
        complexity="single",
        user_input="what paths is this box currently exporting over NFS?",
        notes="Operator wants a quick view of active exports.",
    ),
    Scenario(
        id="nfs-exportfs_list-0005",
        tool="nfs",
        operation="exportfs_list",
        permission_class=_pc("exportfs_list"),
        complexity="diagnostic",
        user_input="after the reload I need to confirm the exports are actually live — check exportfs",
        notes="Post-reload verification that exports published correctly.",
    ),

    # =========================================================================
    # exportfs_add  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nfs-exportfs_add-0001",
        tool="nfs",
        operation="exportfs_add",
        permission_class=_pc("exportfs_add"),
        complexity="single",
        user_input="reload the NFS exports from /etc/exports",
        notes="WRITE: re-publish all exports defined in /etc/exports.",
    ),
    Scenario(
        id="nfs-exportfs_add-0002",
        tool="nfs",
        operation="exportfs_add",
        permission_class=_pc("exportfs_add"),
        complexity="multi",
        user_input="I just added a new share to /etc/exports — apply it without restarting the service",
        notes="Multi-step: re-export after an /etc/exports edit.",
    ),
    Scenario(
        id="nfs-exportfs_add-0003",
        tool="nfs",
        operation="exportfs_add",
        permission_class=_pc("exportfs_add"),
        complexity="single",
        user_input="publish the NFS exports",
        notes="WRITE: simple re-export all.",
    ),
    Scenario(
        id="nfs-exportfs_add-0004",
        tool="nfs",
        operation="exportfs_add",
        permission_class=_pc("exportfs_add"),
        complexity="diagnostic",
        user_input="clients can't see the new /projects share — reload exports to make sure it's active",
        notes="Diagnostic-triggered WRITE: re-publish to fix a share visibility issue.",
    ),
    Scenario(
        id="nfs-exportfs_add-0005",
        tool="nfs",
        operation="exportfs_add",
        permission_class=_pc("exportfs_add"),
        complexity="multi",
        user_input="refresh the NFS exports and then list the active ones to confirm",
        notes="Multi-step: reload exports then verify with exportfs_list.",
    ),

    # =========================================================================
    # exportfs_unexport  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="nfs-exportfs_unexport-0001",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="single",
        user_input="revoke the NFS export of /srv/nfs/data to all clients",
        notes="DESTRUCTIVE: unexport a share — cuts off all clients using it.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-0002",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="single",
        user_input="remove the NFS export for 192.168.1.0/24:/srv/nfs/backups",
        notes="DESTRUCTIVE: unexport a share for a specific subnet.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-0003",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="diagnostic",
        user_input="the /legacy share is no longer needed — unexport it now so clients stop depending on it",
        notes="DESTRUCTIVE: clean up an obsolete export path.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-0004",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="multi",
        user_input="unexport /srv/nfs/tmp for the dev subnet and then list what's still exported",
        notes="Multi-step DESTRUCTIVE: revoke a single export then verify remaining exports.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-0005",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="diagnostic",
        user_input="security says we need to immediately revoke the /sensitive share — do it now",
        notes="DESTRUCTIVE: emergency revoke of a sensitive share on security order.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-0006",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("exportfs_unexport"),
        complexity="single",
        user_input="unexport *:/srv/old-data from NFS",
        notes="DESTRUCTIVE: revoke an export across all clients using wildcard.",
    ),

    # =========================================================================
    # exports_view  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="nfs-exports_view-0001",
        tool="nfs",
        operation="exports_view",
        permission_class=_pc("exports_view"),
        complexity="single",
        user_input="show me the contents of /etc/exports",
        notes="Simple READ: display the NFS exports configuration file.",
    ),
    Scenario(
        id="nfs-exports_view-0002",
        tool="nfs",
        operation="exports_view",
        permission_class=_pc("exports_view"),
        complexity="diagnostic",
        user_input="a share isn't mounting — let me see what /etc/exports actually says",
        notes="Diagnostic: read the config to check for typos or missing entries.",
    ),
    Scenario(
        id="nfs-exports_view-0003",
        tool="nfs",
        operation="exports_view",
        permission_class=_pc("exports_view"),
        complexity="multi",
        user_input="look at /etc/exports and then tell me if the /srv/data share has sync enabled",
        notes="Multi-step: view config then interpret a specific option.",
    ),
    Scenario(
        id="nfs-exports_view-0004",
        tool="nfs",
        operation="exports_view",
        permission_class=_pc("exports_view"),
        complexity="single",
        user_input="what exports are configured in /etc/exports on this NFS server?",
        notes="Operator wants the raw configuration content.",
    ),
    Scenario(
        id="nfs-exports_view-0005",
        tool="nfs",
        operation="exports_view",
        permission_class=_pc("exports_view"),
        complexity="diagnostic",
        user_input="we had a misconfigured export — show me /etc/exports so I can review the options",
        notes="Post-incident diagnostic: review export configuration for errors.",
    ),

    # =========================================================================
    # nfs_start  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nfs-nfs_start-0001",
        tool="nfs",
        operation="nfs_start",
        permission_class=_pc("nfs_start"),
        complexity="single",
        user_input="start the NFS server",
        notes="WRITE: start nfs-server.service.",
    ),
    Scenario(
        id="nfs-nfs_start-0002",
        tool="nfs",
        operation="nfs_start",
        permission_class=_pc("nfs_start"),
        complexity="multi",
        user_input="start the NFS server and then check if it came up correctly",
        notes="Multi-step: start then status verification.",
    ),
    Scenario(
        id="nfs-nfs_start-0003",
        tool="nfs",
        operation="nfs_start",
        permission_class=_pc("nfs_start"),
        complexity="diagnostic",
        user_input="clients can't mount anything — the NFS service is down, bring it back up",
        notes="Diagnostic-triggered WRITE: start the NFS service to restore client access.",
    ),
    Scenario(
        id="nfs-nfs_start-0004",
        tool="nfs",
        operation="nfs_start",
        permission_class=_pc("nfs_start"),
        complexity="single",
        user_input="bring the NFS daemon online",
        notes="WRITE: operator wants the NFS daemon running.",
    ),
    Scenario(
        id="nfs-nfs_start-0005",
        tool="nfs",
        operation="nfs_start",
        permission_class=_pc("nfs_start"),
        complexity="multi",
        user_input="start nfs-server and then reload the exports so clients can connect",
        notes="Multi-step: start service then publish exports.",
    ),

    # =========================================================================
    # nfs_stop  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="nfs-nfs_stop-0001",
        tool="nfs",
        operation="nfs_stop",
        permission_class=_pc("nfs_stop"),
        complexity="single",
        user_input="stop the NFS server for maintenance",
        notes="WRITE: stop nfs-server.service for a planned maintenance window.",
    ),
    Scenario(
        id="nfs-nfs_stop-0002",
        tool="nfs",
        operation="nfs_stop",
        permission_class=_pc("nfs_stop"),
        complexity="multi",
        user_input="stop the NFS server and confirm it has exited cleanly",
        notes="Multi-step: stop then verify the service is no longer running.",
    ),
    Scenario(
        id="nfs-nfs_stop-0003",
        tool="nfs",
        operation="nfs_stop",
        permission_class=_pc("nfs_stop"),
        complexity="diagnostic",
        user_input="NFS is causing high CPU — stop it so we can investigate",
        notes="Diagnostic-triggered WRITE: stop NFS to isolate a performance issue.",
    ),
    Scenario(
        id="nfs-nfs_stop-0004",
        tool="nfs",
        operation="nfs_stop",
        permission_class=_pc("nfs_stop"),
        complexity="single",
        user_input="take the NFS service offline",
        notes="WRITE: operator wants the NFS service stopped.",
    ),
    Scenario(
        id="nfs-nfs_stop-0005",
        tool="nfs",
        operation="nfs_stop",
        permission_class=_pc("nfs_stop"),
        complexity="multi",
        user_input="shut down the NFS daemon and then update the exports file before bringing it back",
        notes="Multi-step: stop service, then config change, then restart.",
    ),

    # =========================================================================
    # mount_client  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="nfs-mount_client-0001",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="single",
        user_input="mount fileserver.corp.local:/srv/nfs/data to /mnt/data",
        notes="WRITE: basic NFS client mount.",
    ),
    Scenario(
        id="nfs-mount_client-0002",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="single",
        user_input="mount 192.168.1.50:/backups on /mnt/backups",
        notes="WRITE: mount a backup share from a remote host by IP.",
    ),
    Scenario(
        id="nfs-mount_client-0003",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="multi",
        user_input="check what nas01 exports and then mount the /data share to /mnt/nas-data",
        notes="Multi-step: showmount to verify, then mount.",
    ),
    Scenario(
        id="nfs-mount_client-0004",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="diagnostic",
        user_input="the build system needs access to the artifact store — mount storage.internal:/artifacts at /mnt/artifacts",
        notes="Diagnostic context: mount a share needed to unblock a workflow.",
    ),
    Scenario(
        id="nfs-mount_client-0005",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="single",
        user_input="attach the shared /logs directory from logserver.internal at /var/log/remote",
        notes="WRITE: mount a remote log aggregation share.",
    ),
    Scenario(
        id="nfs-mount_client-0006",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="multi",
        user_input="mount filer02:/projects at /mnt/projects and then verify the mount is accessible",
        notes="Multi-step: mount then confirm accessibility.",
    ),
    Scenario(
        id="nfs-mount_client-0007",
        tool="nfs",
        operation="mount_client",
        permission_class=_pc("mount_client"),
        complexity="diagnostic",
        user_input="the deployment script can't find /mnt/shared — mount netstore.corp.local:/shared there",
        notes="Diagnostic: mount a missing share to fix a failing deployment.",
    ),
]


# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("nfs").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "nfs", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("nfs").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
