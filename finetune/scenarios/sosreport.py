"""finetune/scenarios/sosreport.py — Scenario corpus for the 'sosreport' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  generate  WRITE  — run 'sos report' to collect a system diagnostics archive
  info      READ   — list available sos plugins and their status

Coverage targets
----------------
  >= 40 entries total across both operations.
  All three complexities represented: single | multi | diagnostic.

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
# Scenario dataclass — field names match the canonical JOIN shape exactly
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
    """Return the live permission class for a sosreport operation."""
    return registry.get("sosreport").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # generate  (WRITE) — 25 entries
    # =========================================================================

    Scenario(
        id="sosreport-generate-0001",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="generate a sosreport on this host",
        notes="Basic sosreport collection with no extra options.",
    ),
    Scenario(
        id="sosreport-generate-0002",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="collect a sos report and save it to /tmp",
        notes="Generate archive to a custom output directory.",
    ),
    Scenario(
        id="sosreport-generate-0003",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="run sos report with the label 'case-123456'",
        notes="Labelled archive for a support case.",
    ),
    Scenario(
        id="sosreport-generate-0004",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="create a sos report for the support ticket",
        notes="Standard support archive collection.",
    ),
    Scenario(
        id="sosreport-generate-0005",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="gather system diagnostics into a sos archive",
        notes="Generic system diagnostics collection request.",
    ),
    Scenario(
        id="sosreport-generate-0006",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="generate a sosreport and then tell me the path to the archive",
        notes="Multi-step: generate archive, then parse/report the path.",
    ),
    Scenario(
        id="sosreport-generate-0007",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="collect a sos report labelled 'pre-upgrade' and save it to /var/tmp before we do the OS update",
        notes="Multi-step: pre-upgrade diagnostic snapshot, then proceed with maintenance.",
    ),
    Scenario(
        id="sosreport-generate-0008",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="the system is behaving oddly — collect a sosreport so we can send it to support",
        notes="Diagnostic-triggered WRITE: evidence collection for incident investigation.",
    ),
    Scenario(
        id="sosreport-generate-0009",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="performance is degraded — gather a sos report before rebooting",
        notes="Diagnostic: capture state before a corrective reboot.",
    ),
    Scenario(
        id="sosreport-generate-0010",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="run sos report non-interactively and label it 'nightly-check'",
        notes="Batch-mode collection with a descriptive label.",
    ),
    Scenario(
        id="sosreport-generate-0011",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="take a sos snapshot of this server for compliance records",
        notes="Compliance-driven diagnostic collection.",
    ),
    Scenario(
        id="sosreport-generate-0012",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="collect the sos report and then show me what plugins ran",
        notes="Multi-step: generate archive, then inspect stdout for plugin list.",
    ),
    Scenario(
        id="sosreport-generate-0013",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="kernel oops appeared in dmesg — capture a sosreport immediately",
        notes="Diagnostic: urgent evidence capture after a kernel fault.",
    ),
    Scenario(
        id="sosreport-generate-0014",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="generate a sos report to /mnt/nfs/reports with label 'node3'",
        notes="Custom output directory on a network-mounted share.",
    ),
    Scenario(
        id="sosreport-generate-0015",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="run a sos report collection to help diagnose the disk I/O issue",
        notes="Storage-related incident — sos archive for offline analysis.",
    ),
    Scenario(
        id="sosreport-generate-0016",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="the network is intermittently dropping — collect sos report before the next outage window",
        notes="Diagnostic: network instability evidence capture.",
    ),
    Scenario(
        id="sosreport-generate-0017",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="gather sos data labelled 'post-incident' and confirm the archive was written",
        notes="Multi-step: post-incident collection, then verify archive exists.",
    ),
    Scenario(
        id="sosreport-generate-0018",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="collect diagnostics for the Red Hat support case",
        notes="Support case archive — standard workflow.",
    ),
    Scenario(
        id="sosreport-generate-0019",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="run sos report on this host with label 'db-primary'",
        notes="Database primary node diagnostic snapshot.",
    ),
    Scenario(
        id="sosreport-generate-0020",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="a service keeps crashing — grab the sos data before we restart it",
        notes="Diagnostic: preserve state before a remediation action.",
    ),
    Scenario(
        id="sosreport-generate-0021",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="collect a sos report, then show the size of the resulting archive",
        notes="Multi-step: generate then report archive size from stdout.",
    ),
    Scenario(
        id="sosreport-generate-0022",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="take a sos snapshot before applying the security patch",
        notes="Pre-patch baseline capture for rollback reference.",
    ),
    Scenario(
        id="sosreport-generate-0023",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="diagnostic",
        user_input="memory usage is at 95% — capture a sosreport for analysis",
        notes="Diagnostic: high-memory-pressure evidence collection.",
    ),
    Scenario(
        id="sosreport-generate-0024",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="single",
        user_input="generate a sos report to /var/tmp with label 'selinux-issue'",
        notes="SELinux-related incident — labelled archive for targeted review.",
    ),
    Scenario(
        id="sosreport-generate-0025",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("generate"),
        complexity="multi",
        user_input="collect sos data for both the networking and kernel plugins, then verify the archive path",
        notes="Multi-step: generate full archive (all plugins run by default), verify output.",
    ),

    # =========================================================================
    # info  (READ) — 20 entries
    # =========================================================================

    Scenario(
        id="sosreport-info-0001",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me the available sos plugins on this system",
        notes="Full plugin listing — no specific plugin requested.",
    ),
    Scenario(
        id="sosreport-info-0002",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what sos plugins are enabled?",
        notes="Operator wants to know which plugins will run in a report.",
    ),
    Scenario(
        id="sosreport-info-0003",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show details for the networking sos plugin",
        notes="Single-plugin inspection — networking diagnostics.",
    ),
    Scenario(
        id="sosreport-info-0004",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="describe the kernel sos plugin",
        notes="Single-plugin inspection — kernel data collection.",
    ),
    Scenario(
        id="sosreport-info-0005",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="list all sos plugins that collect storage data",
        notes="Read-only enumeration — operator filtering for storage plugins.",
    ),
    Scenario(
        id="sosreport-info-0006",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="list all sos plugins and tell me which ones are disabled",
        notes="Multi-step: list plugins then filter for disabled entries.",
    ),
    Scenario(
        id="sosreport-info-0007",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="we suspect the selinux plugin might not be collecting data — check if it is enabled in sos",
        notes="Diagnostic: verify plugin enablement for an ongoing investigation.",
    ),
    Scenario(
        id="sosreport-info-0008",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show the sos info for the logs plugin",
        notes="Single-plugin inspection — log collection plugin details.",
    ),
    Scenario(
        id="sosreport-info-0009",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what version of sos is installed and what plugins does it have?",
        notes="Capability audit — sos version and plugin inventory.",
    ),
    Scenario(
        id="sosreport-info-0010",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="we need to confirm that the subscription plugin is available before collecting a support report",
        notes="Diagnostic: pre-collection plugin availability check.",
    ),
    Scenario(
        id="sosreport-info-0011",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="check sos plugin info for the rpm plugin",
        notes="Single-plugin inspection — RPM package data collection.",
    ),
    Scenario(
        id="sosreport-info-0012",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me details about the hardware sos plugin",
        notes="Single-plugin inspection — hardware inventory collection.",
    ),
    Scenario(
        id="sosreport-info-0013",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="check sos plugin info for the block plugin and then generate a report if the plugin is enabled",
        notes="Multi-step: read-check then conditional write.",
    ),
    Scenario(
        id="sosreport-info-0014",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="is the pacemaker plugin available in sos on this node?",
        notes="Cluster-related plugin availability check.",
    ),
    Scenario(
        id="sosreport-info-0015",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="the last sosreport seemed incomplete — check which plugins are available",
        notes="Diagnostic: investigate incomplete report by reviewing plugin set.",
    ),
    Scenario(
        id="sosreport-info-0016",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show sos plugin details for the podman plugin",
        notes="Single-plugin inspection — container runtime data collection.",
    ),
    Scenario(
        id="sosreport-info-0017",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="list every sos plugin and how many are enabled vs disabled",
        notes="READ inventory of plugin states for capacity planning.",
    ),
    Scenario(
        id="sosreport-info-0018",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="confirm the auditd plugin is active in sos before filing the security report",
        notes="Diagnostic: compliance-driven plugin verification.",
    ),
    Scenario(
        id="sosreport-info-0019",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show sos info for the boot plugin",
        notes="Single-plugin inspection — boot and initrd data collection.",
    ),
    Scenario(
        id="sosreport-info-0020",
        tool="sosreport",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="list sos plugins and then run a report including the selinux and kernel plugins",
        notes="Multi-step: enumerate plugins then generate archive.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("sosreport").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "sosreport", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("sosreport").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
