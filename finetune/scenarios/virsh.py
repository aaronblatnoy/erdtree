"""finetune/scenarios/virsh.py — Scenario corpus for the 'virsh' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list         READ        — list all defined virtual machine domains
  dominfo      READ        — show detailed info for a domain
  start        WRITE       — start a defined domain
  shutdown     WRITE       — gracefully shut down a running domain
  define       WRITE       — define a new domain from an XML file
  destroy      DESTRUCTIVE — forcibly power off a running domain
  undefine     DESTRUCTIVE — remove a domain definition (optionally delete storage)
  pool-list    READ        — list all storage pools
  pool-define  WRITE       — define a storage pool from an XML file
  pool-destroy DESTRUCTIVE — stop and destroy a storage pool

Coverage targets
----------------
  >= 40 entries total across all 10 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the require-confirmation-before-destructive-op gate.

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
# Field names are EXACT for Phase-13 JOIN compatibility.
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
    """Return the live permission class for a virsh operation."""
    return registry.get("virsh").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-list-0001",
        tool="virsh",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all virtual machines on this host",
        notes="Simple read: list all KVM domains regardless of state.",
    ),
    Scenario(
        id="virsh-list-0002",
        tool="virsh",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="which VMs are running right now?",
        notes="Admin wants a quick overview of VM states.",
    ),
    Scenario(
        id="virsh-list-0003",
        tool="virsh",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all VMs and then show me which ones are shut off",
        notes="Multi-step: list domains, then filter for shut-off state.",
    ),
    Scenario(
        id="virsh-list-0004",
        tool="virsh",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the hypervisor is acting strange — first list all domains to see what's running",
        notes="Diagnostic entry point: list all VMs before investigating further.",
    ),
    Scenario(
        id="virsh-list-0005",
        tool="virsh",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="how many virtual machines are defined on this KVM host?",
        notes="Read: enumerate defined domains to get a count.",
    ),

    # =========================================================================
    # dominfo  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-dominfo-0001",
        tool="virsh",
        operation="dominfo",
        permission_class=_pc("dominfo"),
        complexity="single",
        user_input="show me info for the centos9-web VM",
        notes="Read: inspect domain metadata for a specific VM.",
    ),
    Scenario(
        id="virsh-dominfo-0002",
        tool="virsh",
        operation="dominfo",
        permission_class=_pc("dominfo"),
        complexity="single",
        user_input="how much memory is allocated to the rhel9-db virtual machine?",
        notes="Read: check resource allocation for a named domain.",
    ),
    Scenario(
        id="virsh-dominfo-0003",
        tool="virsh",
        operation="dominfo",
        permission_class=_pc("dominfo"),
        complexity="single",
        user_input="what is the UUID of the ubuntu22-test VM?",
        notes="Read: retrieve domain UUID for scripting or inventory.",
    ),
    Scenario(
        id="virsh-dominfo-0004",
        tool="virsh",
        operation="dominfo",
        permission_class=_pc("dominfo"),
        complexity="multi",
        user_input="get the domain info for fedora38-dev and check if it has autostart enabled",
        notes="Multi-step: dominfo then check the Autostart field.",
    ),
    Scenario(
        id="virsh-dominfo-0005",
        tool="virsh",
        operation="dominfo",
        permission_class=_pc("dominfo"),
        complexity="diagnostic",
        user_input="the centos9-web VM is unresponsive — pull its domain info to check its reported state",
        notes="Diagnostic: check domain state before deciding on remediation.",
    ),

    # =========================================================================
    # start  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-start-0001",
        tool="virsh",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start the centos9-web VM",
        notes="WRITE: start a stopped VM.",
    ),
    Scenario(
        id="virsh-start-0002",
        tool="virsh",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="bring up the rhel9-db virtual machine",
        notes="WRITE: start a database VM for a planned maintenance window.",
    ),
    Scenario(
        id="virsh-start-0003",
        tool="virsh",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start the fedora38-dev VM and then check that it is running",
        notes="Multi-step: start domain then confirm via list.",
    ),
    Scenario(
        id="virsh-start-0004",
        tool="virsh",
        operation="start",
        permission_class=_pc("start"),
        complexity="diagnostic",
        user_input="the dev environment is down — start the ubuntu22-test VM if it is stopped",
        notes="Diagnostic-triggered WRITE: conditional start based on prior list check.",
    ),
    Scenario(
        id="virsh-start-0005",
        tool="virsh",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="power on the windows2019-ad domain controller VM",
        notes="WRITE: start a Windows domain controller VM.",
    ),

    # =========================================================================
    # shutdown  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-shutdown-0001",
        tool="virsh",
        operation="shutdown",
        permission_class=_pc("shutdown"),
        complexity="single",
        user_input="gracefully shut down the centos9-web VM",
        notes="WRITE: clean shutdown of a running VM.",
    ),
    Scenario(
        id="virsh-shutdown-0002",
        tool="virsh",
        operation="shutdown",
        permission_class=_pc("shutdown"),
        complexity="single",
        user_input="send a shutdown signal to the rhel9-db virtual machine for maintenance",
        notes="WRITE: planned shutdown before disk maintenance.",
    ),
    Scenario(
        id="virsh-shutdown-0003",
        tool="virsh",
        operation="shutdown",
        permission_class=_pc("shutdown"),
        complexity="multi",
        user_input="shut down the fedora38-dev VM and then verify it has stopped",
        notes="Multi-step: shutdown then confirm state via list.",
    ),
    Scenario(
        id="virsh-shutdown-0004",
        tool="virsh",
        operation="shutdown",
        permission_class=_pc("shutdown"),
        complexity="diagnostic",
        user_input="the ubuntu22-test VM is misbehaving — attempt a clean shutdown first before anything else",
        notes="Diagnostic: attempt graceful shutdown before considering force-stop.",
    ),
    Scenario(
        id="virsh-shutdown-0005",
        tool="virsh",
        operation="shutdown",
        permission_class=_pc("shutdown"),
        complexity="single",
        user_input="stop the windows2019-ad VM cleanly so we can take a snapshot",
        notes="WRITE: graceful shutdown before snapshot — avoids data corruption.",
    ),

    # =========================================================================
    # define  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="virsh-define-0001",
        tool="virsh",
        operation="define",
        permission_class=_pc("define"),
        complexity="single",
        user_input="define a new VM from /tmp/centos9-vm.xml",
        notes="WRITE: register a new domain definition from an XML file.",
    ),
    Scenario(
        id="virsh-define-0002",
        tool="virsh",
        operation="define",
        permission_class=_pc("define"),
        complexity="single",
        user_input="register the domain described in /etc/libvirt/qemu/rhel9-db.xml",
        notes="WRITE: define domain from an existing system XML file.",
    ),
    Scenario(
        id="virsh-define-0003",
        tool="virsh",
        operation="define",
        permission_class=_pc("define"),
        complexity="multi",
        user_input="define the VM from /tmp/new-vm.xml and then start it",
        notes="Multi-step: define domain then immediately start it.",
    ),
    Scenario(
        id="virsh-define-0004",
        tool="virsh",
        operation="define",
        permission_class=_pc("define"),
        complexity="diagnostic",
        user_input="the staging VM disappeared from the list — redefine it from /backup/staging-vm.xml",
        notes="Diagnostic-triggered WRITE: restore a domain definition from backup XML.",
    ),

    # =========================================================================
    # destroy  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-destroy-0001",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("destroy"),
        complexity="single",
        user_input="force power off the centos9-web VM immediately",
        notes="DESTRUCTIVE: abrupt power-off of a running VM — risks in-flight data loss.",
    ),
    Scenario(
        id="virsh-destroy-0002",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("destroy"),
        complexity="single",
        user_input="kill the rhel9-db virtual machine right now, it is completely hung",
        notes="DESTRUCTIVE: emergency hard stop of a hung VM.",
    ),
    Scenario(
        id="virsh-destroy-0003",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("destroy"),
        complexity="multi",
        user_input="the ubuntu22-test VM is not responding to shutdown — destroy it and then check it is gone",
        notes="Multi-step: force destroy after graceful shutdown failed, confirm via list.",
    ),
    Scenario(
        id="virsh-destroy-0004",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("destroy"),
        complexity="diagnostic",
        user_input="the fedora38-dev VM has been unresponsive for 30 minutes — try shutdown first, then destroy if needed",
        notes="Diagnostic: escalated remediation path ending in forced power-off.",
    ),
    Scenario(
        id="virsh-destroy-0005",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("destroy"),
        complexity="single",
        user_input="immediately cut power to the windows2019-ad VM — it is running malicious code",
        notes="DESTRUCTIVE: security-triggered emergency shutdown via virsh destroy.",
    ),

    # =========================================================================
    # undefine  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-undefine-0001",
        tool="virsh",
        operation="undefine",
        permission_class=_pc("undefine"),
        complexity="single",
        user_input="remove the definition for the decommissioned centos9-web VM",
        notes="DESTRUCTIVE: undefine domain, keep disk images intact.",
    ),
    Scenario(
        id="virsh-undefine-0002",
        tool="virsh",
        operation="undefine",
        permission_class=_pc("undefine"),
        complexity="single",
        user_input="completely remove the ubuntu22-test VM including its disk images",
        notes="DESTRUCTIVE: undefine with remove_storage=True — permanent disk deletion.",
    ),
    Scenario(
        id="virsh-undefine-0003",
        tool="virsh",
        operation="undefine",
        permission_class=_pc("undefine"),
        complexity="multi",
        user_input="decommission the fedora38-dev VM: shut it down, then remove its definition and all storage",
        notes="Multi-step DESTRUCTIVE: shutdown, then undefine with storage removal.",
    ),
    Scenario(
        id="virsh-undefine-0004",
        tool="virsh",
        operation="undefine",
        permission_class=_pc("undefine"),
        complexity="diagnostic",
        user_input="the old test VM is taking up disk space — remove it and its storage if it is already stopped",
        notes="Diagnostic: verify stopped state before undefining with storage removal.",
    ),
    Scenario(
        id="virsh-undefine-0005",
        tool="virsh",
        operation="undefine",
        permission_class=_pc("undefine"),
        complexity="single",
        user_input="remove the rhel8-legacy VM definition but leave the disk image intact for archiving",
        notes="DESTRUCTIVE: undefine only — disk preserved for separate archival process.",
    ),

    # =========================================================================
    # pool-list  (READ) — 3 entries
    # =========================================================================

    Scenario(
        id="virsh-pool-list-0001",
        tool="virsh",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="single",
        user_input="show all libvirt storage pools on this host",
        notes="Read: list all defined storage pools.",
    ),
    Scenario(
        id="virsh-pool-list-0002",
        tool="virsh",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="multi",
        user_input="list storage pools and check which ones are inactive",
        notes="Multi-step: pool-list then filter for inactive entries.",
    ),
    Scenario(
        id="virsh-pool-list-0003",
        tool="virsh",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="diagnostic",
        user_input="disk creation failed — check what storage pools are available and whether the default pool is active",
        notes="Diagnostic: verify pool availability before troubleshooting VM disk issues.",
    ),

    # =========================================================================
    # pool-define  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="virsh-pool-define-0001",
        tool="virsh",
        operation="pool-define",
        permission_class=_pc("pool-define"),
        complexity="single",
        user_input="define a new libvirt storage pool from /etc/libvirt/storage/images.xml",
        notes="WRITE: register a new storage pool definition from XML.",
    ),
    Scenario(
        id="virsh-pool-define-0002",
        tool="virsh",
        operation="pool-define",
        permission_class=_pc("pool-define"),
        complexity="single",
        user_input="add the NFS-backed pool described in /tmp/nfs-pool.xml",
        notes="WRITE: define an NFS-backed storage pool.",
    ),
    Scenario(
        id="virsh-pool-define-0003",
        tool="virsh",
        operation="pool-define",
        permission_class=_pc("pool-define"),
        complexity="multi",
        user_input="define the backup storage pool from /tmp/backup-pool.xml and then start it",
        notes="Multi-step: define pool then activate it (pool-start not covered here).",
    ),
    Scenario(
        id="virsh-pool-define-0004",
        tool="virsh",
        operation="pool-define",
        permission_class=_pc("pool-define"),
        complexity="diagnostic",
        user_input="the images pool is missing — redefine it from the backup at /backup/images-pool.xml",
        notes="Diagnostic WRITE: recover a lost pool definition from backup XML.",
    ),

    # =========================================================================
    # pool-destroy  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="virsh-pool-destroy-0001",
        tool="virsh",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="destroy the obsolete backup storage pool",
        notes="DESTRUCTIVE: stop and deactivate the storage pool; volumes become inaccessible.",
    ),
    Scenario(
        id="virsh-pool-destroy-0002",
        tool="virsh",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="take the images pool offline — we are migrating storage to new hardware",
        notes="DESTRUCTIVE: planned pool destruction for storage migration.",
    ),
    Scenario(
        id="virsh-pool-destroy-0003",
        tool="virsh",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="multi",
        user_input="destroy the old-nfs pool and then verify it no longer appears in the pool list",
        notes="Multi-step DESTRUCTIVE: destroy pool then confirm removal via pool-list.",
    ),
    Scenario(
        id="virsh-pool-destroy-0004",
        tool="virsh",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="diagnostic",
        user_input="the staging storage pool is corrupted and all VMs using it are shut off — destroy it so we can redefine it cleanly",
        notes="Diagnostic: confirm VMs are stopped before destroying a corrupted pool.",
    ),
    Scenario(
        id="virsh-pool-destroy-0005",
        tool="virsh",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="remove the temp pool from libvirt — it was only needed for the migration and all VMs are moved",
        notes="DESTRUCTIVE: clean-up of a temporary pool after migration is complete.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("virsh").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "virsh", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("virsh").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
