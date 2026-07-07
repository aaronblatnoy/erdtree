"""finetune/scenarios/tuned.py — Scenario corpus for the 'tuned' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list       READ   — list all available tuned profiles
  active     READ   — show the currently active tuned profile
  recommend  READ   — show the recommended tuned profile for this system
  profile    WRITE  — switch to a named tuned profile
  off        WRITE  — deactivate the current tuned profile

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
    """Return the live permission class for a tuned operation."""
    return registry.get("tuned").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="tuned-list-0001",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all available tuning profiles",
        notes="Simple read: enumerate all tuned profiles installed on this host.",
    ),
    Scenario(
        id="tuned-list-0002",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what tuned profiles are available on this system?",
        notes="Operator wants to know what profiles exist before choosing one.",
    ),
    Scenario(
        id="tuned-list-0003",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the performance tuning profiles I can apply",
        notes="Operator phrasing around applying a profile — read first.",
    ),
    Scenario(
        id="tuned-list-0004",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list the available tuned profiles and then tell me which one is active",
        notes="Multi-step: list all profiles, then show the currently active one.",
    ),
    Scenario(
        id="tuned-list-0005",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the system is underperforming — what tuning profiles are installed?",
        notes="Diagnostic entry point: enumerate profiles as first step in performance triage.",
    ),
    Scenario(
        id="tuned-list-0006",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show tuned-adm list output",
        notes="Direct CLI-style request to run tuned-adm list.",
    ),
    Scenario(
        id="tuned-list-0007",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show me all tuned profiles, then recommend one for a database workload",
        notes="Multi-step: list then recommend — operator sizing a DB host.",
    ),
    Scenario(
        id="tuned-list-0008",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I want to tune this host for low latency — first show me what profiles exist",
        notes="Diagnostic: operator exploring options before making a write decision.",
    ),
    Scenario(
        id="tuned-list-0009",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="are there any realtime tuning profiles available?",
        notes="Operator looking for realtime profiles specifically — list to confirm.",
    ),
    Scenario(
        id="tuned-list-0010",
        tool="tuned",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all tuned profiles, show the active one, and apply the recommended one if it differs",
        notes="Multi-step: list, active, recommend, conditionally profile — full workflow.",
    ),

    # =========================================================================
    # active  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="tuned-active-0001",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="single",
        user_input="what tuned profile is currently active?",
        notes="Basic read: show the currently applied tuning profile.",
    ),
    Scenario(
        id="tuned-active-0002",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="single",
        user_input="show me the active tuning profile on this host",
        notes="Common sysadmin check — verify which profile is running.",
    ),
    Scenario(
        id="tuned-active-0003",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="single",
        user_input="is any tuning profile currently applied to this server?",
        notes="Operator checking whether tuning is in effect at all.",
    ),
    Scenario(
        id="tuned-active-0004",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="diagnostic",
        user_input="the server has unexpected CPU behaviour — check what tuned profile is active",
        notes="Diagnostic: verify the applied profile as part of performance investigation.",
    ),
    Scenario(
        id="tuned-active-0005",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="multi",
        user_input="check the active tuned profile and compare it with what is recommended",
        notes="Multi-step: active then recommend, compare outputs.",
    ),
    Scenario(
        id="tuned-active-0006",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="single",
        user_input="run tuned-adm active for me",
        notes="Direct CLI delegation — operator knows the command.",
    ),
    Scenario(
        id="tuned-active-0007",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="diagnostic",
        user_input="high latency reported on this NVMe node — confirm the active tuning profile",
        notes="Diagnostic: check profile is latency-performance or similar on a storage host.",
    ),
    Scenario(
        id="tuned-active-0008",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="multi",
        user_input="show the active profile and then switch to throughput-performance if it is different",
        notes="Multi-step: read active then conditionally write profile — operator workflow.",
    ),
    Scenario(
        id="tuned-active-0009",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="single",
        user_input="was a tuning profile ever applied to this box?",
        notes="Operator auditing a freshly provisioned host for baseline tuning state.",
    ),
    Scenario(
        id="tuned-active-0010",
        tool="tuned",
        operation="active",
        permission_class=_pc("active"),
        complexity="diagnostic",
        user_input="we have a compliance audit tomorrow — confirm which tuned profile is set on each host",
        notes="Diagnostic: compliance check of tuning policy across a fleet.",
    ),

    # =========================================================================
    # recommend  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="tuned-recommend-0001",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="single",
        user_input="what tuned profile does this system recommend?",
        notes="Simple read: ask tuned to recommend a profile based on system detection.",
    ),
    Scenario(
        id="tuned-recommend-0002",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="single",
        user_input="suggest the best tuning profile for this hardware",
        notes="Operator wants tuned to auto-detect the right profile.",
    ),
    Scenario(
        id="tuned-recommend-0003",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="multi",
        user_input="find the recommended tuned profile and apply it if it is not already active",
        notes="Multi-step: recommend then conditionally profile — common post-install workflow.",
    ),
    Scenario(
        id="tuned-recommend-0004",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="diagnostic",
        user_input="this is a virtual machine — what profile should tuned use?",
        notes="Diagnostic: determine appropriate profile for a VM context.",
    ),
    Scenario(
        id="tuned-recommend-0005",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="single",
        user_input="run tuned-adm recommend",
        notes="Direct CLI delegation.",
    ),
    Scenario(
        id="tuned-recommend-0006",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="multi",
        user_input="get the tuned recommendation, show the active profile, and tell me if they match",
        notes="Multi-step: compare recommended vs active profiles for drift detection.",
    ),
    Scenario(
        id="tuned-recommend-0007",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="diagnostic",
        user_input="we just migrated this host from virtual-guest to bare-metal — what profile does tuned suggest now?",
        notes="Diagnostic: check whether the profile recommendation changed after hardware migration.",
    ),
    Scenario(
        id="tuned-recommend-0008",
        tool="tuned",
        operation="recommend",
        permission_class=_pc("recommend"),
        complexity="single",
        user_input="what is the best out-of-the-box tuning for a new Rocky 9 server?",
        notes="Operator asking for the recommended baseline profile on a fresh install.",
    ),

    # =========================================================================
    # profile  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="tuned-profile-0001",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="apply the throughput-performance profile",
        notes="WRITE: switch to throughput-performance — common on high-traffic servers.",
    ),
    Scenario(
        id="tuned-profile-0002",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="set the tuned profile to latency-performance",
        notes="WRITE: switch to latency-performance for low-latency workloads.",
    ),
    Scenario(
        id="tuned-profile-0003",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="apply the virtual-guest profile on this VM",
        notes="WRITE: virtual-guest is the recommended profile for guest VMs.",
    ),
    Scenario(
        id="tuned-profile-0004",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="switch tuned to the balanced profile",
        notes="WRITE: balanced is a conservative default for mixed workloads.",
    ),
    Scenario(
        id="tuned-profile-0005",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="tune this host for postgresql workloads",
        notes="WRITE: apply the postgresql profile for a dedicated DB host.",
    ),
    Scenario(
        id="tuned-profile-0006",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="multi",
        user_input="apply throughput-performance and then verify the active profile",
        notes="Multi-step: profile write then active read to confirm application.",
    ),
    Scenario(
        id="tuned-profile-0007",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="diagnostic",
        user_input="disk throughput is poor on this storage node — apply the network-throughput profile",
        notes="Diagnostic-triggered WRITE: apply a profile as a remediation step.",
    ),
    Scenario(
        id="tuned-profile-0008",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="set tuned to powersave mode on this laptop",
        notes="WRITE: apply powersave profile for power-constrained hosts.",
    ),
    Scenario(
        id="tuned-profile-0009",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="multi",
        user_input="check what profile is recommended, then apply it",
        notes="Multi-step: recommend read followed by profile write — post-install tuning.",
    ),
    Scenario(
        id="tuned-profile-0010",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="single",
        user_input="apply the hpc-compute profile on this HPC node",
        notes="WRITE: hpc-compute is tailored for compute-heavy workloads.",
    ),
    Scenario(
        id="tuned-profile-0011",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="diagnostic",
        user_input="we are seeing high interrupt latency — switch to the realtime profile",
        notes="Diagnostic-triggered WRITE: switch to realtime profile for latency-sensitive workloads.",
    ),
    Scenario(
        id="tuned-profile-0012",
        tool="tuned",
        operation="profile",
        permission_class=_pc("profile"),
        complexity="multi",
        user_input="apply oracle profile and confirm it took effect by checking the active profile",
        notes="Multi-step: write profile then verify with active read.",
    ),

    # =========================================================================
    # off  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="tuned-off-0001",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="single",
        user_input="turn off tuned on this server",
        notes="WRITE: disable the active tuning profile.",
    ),
    Scenario(
        id="tuned-off-0002",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="single",
        user_input="disable the active tuned profile",
        notes="WRITE: deactivate tuning — operator wants a clean baseline state.",
    ),
    Scenario(
        id="tuned-off-0003",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="multi",
        user_input="turn tuned off and then confirm no profile is active",
        notes="Multi-step: off then active read to confirm deactivation.",
    ),
    Scenario(
        id="tuned-off-0004",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="diagnostic",
        user_input="we suspect the tuning profile is causing intermittent latency spikes — disable it temporarily",
        notes="Diagnostic-triggered WRITE: disable tuning as an isolation step.",
    ),
    Scenario(
        id="tuned-off-0005",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="single",
        user_input="run tuned-adm off",
        notes="WRITE: direct CLI delegation to deactivate all tuning.",
    ),
    Scenario(
        id="tuned-off-0006",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="multi",
        user_input="disable tuned, check the active profile is cleared, then re-apply latency-performance",
        notes="Multi-step: off, verify, then re-apply — operator cycling profiles for testing.",
    ),
    Scenario(
        id="tuned-off-0007",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="diagnostic",
        user_input="performance benchmark results are inconsistent — remove any tuning profile to get a raw baseline",
        notes="Diagnostic: disable tuning to establish an untuned baseline for benchmarking.",
    ),
    Scenario(
        id="tuned-off-0008",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="single",
        user_input="clear the tuning profile from this host",
        notes="WRITE: operator wants a neutral tuning state before decommissioning.",
    ),
    Scenario(
        id="tuned-off-0009",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="multi",
        user_input="what profile is active? if one is set, disable it",
        notes="Multi-step: read active, then conditionally run off.",
    ),
    Scenario(
        id="tuned-off-0010",
        tool="tuned",
        operation="off",
        permission_class=_pc("off"),
        complexity="diagnostic",
        user_input="the oracle profile was applied by a previous admin — disable it so we can assess the raw kernel settings",
        notes="Diagnostic-triggered WRITE: remove an unknown profile before assessment.",
    ),
]


# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("tuned").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "tuned", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("tuned").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
