"""finetune/scenarios/perf.py — Scenario corpus for the 'perf' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  stat    READ   — run perf stat to count hardware events for a command
  top     READ   — show live CPU hotspot data via perf top --stdio
  record  WRITE  — record perf events to perf.data for later analysis

Coverage targets
----------------
  >= 40 entries total across all 3 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios honestly labeled so downstream traces teach the
  confirm-before-write gate.

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
# Compatible field names are EXACT so the P13 JOIN can unify without renames.
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
    """Return the live permission class for a perf operation."""
    return registry.get("perf").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # stat  (READ) — 18 entries
    # =========================================================================

    Scenario(
        id="perf-stat-0001",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="run perf stat on sleep 1 and show me the hardware counters",
        notes="Baseline perf stat on a trivial command to observe counter overhead.",
    ),
    Scenario(
        id="perf-stat-0002",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="how many CPU cycles does 'ls /var/log' use?",
        notes="Simple cycle count on a common filesystem operation.",
    ),
    Scenario(
        id="perf-stat-0003",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="measure instructions per cycle for the gzip command",
        notes="IPC measurement to assess computational efficiency.",
    ),
    Scenario(
        id="perf-stat-0004",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="check cache miss rate when running make in the build directory",
        notes="Cache miss profiling for a build workload.",
    ),
    Scenario(
        id="perf-stat-0005",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="count branch mispredictions for the python3 script",
        notes="Branch predictor efficiency check for a script.",
    ),
    Scenario(
        id="perf-stat-0006",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="get perf stat for 'dd if=/dev/zero of=/dev/null bs=1M count=100'",
        notes="I/O throughput counter check using dd.",
    ),
    Scenario(
        id="perf-stat-0007",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="profile cycles and instructions for the openssl speed test",
        notes="Crypto workload perf stat with specific events.",
    ),
    Scenario(
        id="perf-stat-0008",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="multi",
        user_input="run perf stat on our compression script and compare cycles to last week's baseline",
        notes="Multi-step: stat then compare to a stored baseline for regression detection.",
    ),
    Scenario(
        id="perf-stat-0009",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="multi",
        user_input="measure branch miss rate for the new sort implementation and check if it is worse than the old one",
        notes="Multi-step: stat then compare branch-miss metrics between implementations.",
    ),
    Scenario(
        id="perf-stat-0010",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="diagnostic",
        user_input="the web server response times spiked — run perf stat on an apache worker to find which counter is elevated",
        notes="Diagnostic: use perf stat to identify the bottleneck counter during a latency spike.",
    ),
    Scenario(
        id="perf-stat-0011",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="diagnostic",
        user_input="the database query is slow — get hardware counters to see if it is cache-bound",
        notes="Diagnostic: perf stat to distinguish cache-bound vs compute-bound slow query.",
    ),
    Scenario(
        id="perf-stat-0012",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="count context switches while running the java application for 5 seconds",
        notes="Context switch count for a Java process.",
    ),
    Scenario(
        id="perf-stat-0013",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="how many page faults occur when loading the nginx config?",
        notes="Page fault count during config parsing.",
    ),
    Scenario(
        id="perf-stat-0014",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="measure TLB misses for the memory-intensive data processing job",
        notes="TLB miss rate profiling for a memory-intensive workload.",
    ),
    Scenario(
        id="perf-stat-0015",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="multi",
        user_input="run perf stat 5 times on the benchmark script and give me the averaged results",
        notes="Multi-run stat with repeat averaging for stable measurements.",
    ),
    Scenario(
        id="perf-stat-0016",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="diagnostic",
        user_input="CPU utilization is at 90% but throughput is low — use perf stat to check IPC",
        notes="Diagnostic: IPC below 1.0 implies the workload is stall-bound.",
    ),
    Scenario(
        id="perf-stat-0017",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="get the L1 data cache load miss count for the matrix multiply benchmark",
        notes="L1-dcache miss profiling for a compute-heavy workload.",
    ),
    Scenario(
        id="perf-stat-0018",
        tool="perf",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="diagnostic",
        user_input="the build system is slower after the last kernel upgrade — compare perf stat on make clean between old and new",
        notes="Diagnostic: regression hunt after a kernel upgrade using perf stat comparison.",
    ),

    # =========================================================================
    # top  (READ) — 14 entries
    # =========================================================================

    Scenario(
        id="perf-top-0001",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="show me the top CPU hotspots on this host right now",
        notes="Live CPU hotspot view using perf top in stdio mode.",
    ),
    Scenario(
        id="perf-top-0002",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="which function is using the most CPU cycles at this moment?",
        notes="Function-level CPU cycle attribution.",
    ),
    Scenario(
        id="perf-top-0003",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="run perf top for 30 seconds and show me the overhead breakdown",
        notes="Extended perf top run for a steady-state view.",
    ),
    Scenario(
        id="perf-top-0004",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="CPU is pegged at 100% — use perf top to find the hot function",
        notes="Diagnostic: identify the function responsible for a CPU saturation event.",
    ),
    Scenario(
        id="perf-top-0005",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="the kernel is consuming unexpected CPU — check perf top to see which kernel symbol is hot",
        notes="Diagnostic: kernel CPU attribution via perf top symbol table.",
    ),
    Scenario(
        id="perf-top-0006",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="multi",
        user_input="run perf top then cross-reference the hottest symbol with the source code to find the bottleneck",
        notes="Multi-step: perf top to find the symbol, then source lookup.",
    ),
    Scenario(
        id="perf-top-0007",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="profile the host for 15 seconds sorted by overhead",
        notes="Overhead-sorted perf top for quick triage.",
    ),
    Scenario(
        id="perf-top-0008",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="show CPU hotspots sorted by DSO (shared library)",
        notes="DSO-sorted view to find which library is consuming the most CPU.",
    ),
    Scenario(
        id="perf-top-0009",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="the JVM is slow — run perf top to see if libjvm.so is dominating the CPU",
        notes="Diagnostic: check if JVM native library is the bottleneck.",
    ),
    Scenario(
        id="perf-top-0010",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="use perf top with cache-miss events to find the most cache-unfriendly code",
        notes="Cache-miss-event top for cache efficiency diagnosis.",
    ),
    Scenario(
        id="perf-top-0011",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="multi",
        user_input="take a 20-second perf top snapshot and then record the hottest 5 symbols for the ops report",
        notes="Multi-step: snapshot then extract top-5 symbols for reporting.",
    ),
    Scenario(
        id="perf-top-0012",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="after the last deploy the CPU jumped 30% — run perf top to compare hotspots to the pre-deploy baseline",
        notes="Diagnostic: post-deploy CPU regression identification with perf top.",
    ),
    Scenario(
        id="perf-top-0013",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="display CPU profiling data for 10 seconds on this host",
        notes="Standard 10-second perf top snapshot.",
    ),
    Scenario(
        id="perf-top-0014",
        tool="perf",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="the database backup is taking twice as long as usual — look at perf top while it runs to spot the hot path",
        notes="Diagnostic: correlate backup slowdown with CPU hotspot via perf top.",
    ),

    # =========================================================================
    # record  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="perf-record-0001",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="record perf data for the nginx process for 30 seconds",
        notes="WRITE: capture perf.data for nginx for later perf report analysis.",
    ),
    Scenario(
        id="perf-record-0002",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="run perf record on the make command and save to build-perf.data",
        notes="WRITE: record build workload counters to a named output file.",
    ),
    Scenario(
        id="perf-record-0003",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="capture a 60-second perf recording of the database process",
        notes="WRITE: long-duration recording of the database process.",
    ),
    Scenario(
        id="perf-record-0004",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="multi",
        user_input="record perf data for the web server for 30 seconds, then analyse it with perf report",
        notes="Multi-step WRITE: record then post-process with perf report.",
    ),
    Scenario(
        id="perf-record-0005",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="diagnostic",
        user_input="the API handler is slow — record perf data while I send a burst of requests to capture the hot path",
        notes="Diagnostic-triggered WRITE: capture perf data during a synthetic load spike.",
    ),
    Scenario(
        id="perf-record-0006",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="record cache miss events for the search indexer process",
        notes="WRITE: capture cache-miss events for a specific process.",
    ),
    Scenario(
        id="perf-record-0007",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="save a perf recording of the python data pipeline to /tmp/pipeline.perf.data",
        notes="WRITE: record Python process counters to a custom path.",
    ),
    Scenario(
        id="perf-record-0008",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="multi",
        user_input="record cycle events for java for 45 seconds, then show the top symbols",
        notes="Multi-step WRITE: capture then inspect with perf report.",
    ),
    Scenario(
        id="perf-record-0009",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="diagnostic",
        user_input="I/O wait is elevated during the backup job — record perf events while the backup runs to find the bottleneck",
        notes="Diagnostic-triggered WRITE: capture perf data during a slow backup for I/O analysis.",
    ),
    Scenario(
        id="perf-record-0010",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="single",
        user_input="run perf record on 'openssl speed rsa2048' and save the output",
        notes="WRITE: record perf data for a crypto benchmark command.",
    ),
    Scenario(
        id="perf-record-0011",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="multi",
        user_input="record perf data for the application, then use the data to generate a flamegraph",
        notes="Multi-step WRITE: record then post-process for flamegraph generation.",
    ),
    Scenario(
        id="perf-record-0012",
        tool="perf",
        operation="record",
        permission_class=_pc("record"),
        complexity="diagnostic",
        user_input="the service latency is inconsistent — record perf data over 2 minutes to capture the spikes",
        notes="Diagnostic-triggered WRITE: long-duration capture to catch intermittent spikes.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("perf").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "perf", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("perf").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
