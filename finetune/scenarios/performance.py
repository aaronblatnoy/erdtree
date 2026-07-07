"""finetune/scenarios/performance.py — Scenario corpus for the 'performance' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  sar     READ  — CPU utilization report via sar
  iostat  READ  — disk I/O statistics via iostat
  vmstat  READ  — virtual memory and system statistics via vmstat
  mpstat  READ  — per-CPU utilization statistics via mpstat
  uptime  READ  — system uptime and load averages
  load    READ  — load averages from /proc/loadavg

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
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
# Scenario dataclass — field names EXACT for Phase-13 JOIN compatibility
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
    """Return the live permission class for a performance operation."""
    return registry.get("performance").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # sar  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="performance-sar-0001",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="single",
        user_input="show me the CPU utilization for the last second",
        notes="Single sar sample — quickest CPU check.",
    ),
    Scenario(
        id="performance-sar-0002",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="single",
        user_input="run sar and collect 5 samples at 2-second intervals",
        notes="Multi-sample sar with explicit interval and count.",
    ),
    Scenario(
        id="performance-sar-0003",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="diagnostic",
        user_input="the server feels sluggish — check CPU utilization with sar to see if we're CPU bound",
        notes="Diagnostic: sar as first step in a performance investigation.",
    ),
    Scenario(
        id="performance-sar-0004",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="multi",
        user_input="collect CPU stats for 10 samples at 1-second intervals and then tell me the average idle percentage",
        notes="Multi-step: collect sar data and summarize the average idle.",
    ),
    Scenario(
        id="performance-sar-0005",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="diagnostic",
        user_input="users are reporting slow response times — pull a sar CPU report so I can see if system time is high",
        notes="Diagnostic: correlate application slowness with high %system CPU.",
    ),
    Scenario(
        id="performance-sar-0006",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="single",
        user_input="take one sar snapshot",
        notes="Minimal single-snapshot sar call.",
    ),
    Scenario(
        id="performance-sar-0007",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="multi",
        user_input="run sar every second for 5 seconds and check if iowait is above 10%",
        notes="Multi-step: collect sar and evaluate iowait threshold.",
    ),
    Scenario(
        id="performance-sar-0008",
        tool="performance",
        operation="sar",
        permission_class=_pc("sar"),
        complexity="diagnostic",
        user_input="a batch job finished but the CPU is still pegged — use sar to take a quick snapshot",
        notes="Diagnostic: post-job CPU investigation.",
    ),

    # =========================================================================
    # iostat  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="performance-iostat-0001",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="single",
        user_input="show me disk I/O statistics",
        notes="Single-sample iostat for a quick I/O health check.",
    ),
    Scenario(
        id="performance-iostat-0002",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="single",
        user_input="run iostat with 5 samples at 2-second intervals",
        notes="Multi-sample iostat to observe I/O over time.",
    ),
    Scenario(
        id="performance-iostat-0003",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="diagnostic",
        user_input="the database server is slow — check disk I/O to see if we're hitting a throughput bottleneck",
        notes="Diagnostic: iostat to investigate disk I/O as a cause of slowness.",
    ),
    Scenario(
        id="performance-iostat-0004",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="multi",
        user_input="collect 3 iostat samples and tell me which disk has the highest await time",
        notes="Multi-step: collect iostat and identify highest-latency disk.",
    ),
    Scenario(
        id="performance-iostat-0005",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="diagnostic",
        user_input="I/O wait is at 80% on this host — run iostat to find the saturated device",
        notes="Diagnostic: high iowait — use iostat to pin the culprit device.",
    ),
    Scenario(
        id="performance-iostat-0006",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="single",
        user_input="take a one-shot iostat reading",
        notes="Single snapshot disk I/O check.",
    ),
    Scenario(
        id="performance-iostat-0007",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="multi",
        user_input="run iostat every second for 10 seconds and check if %util on sda is over 90%",
        notes="Multi-step: observe I/O utilization on a specific device over time.",
    ),
    Scenario(
        id="performance-iostat-0008",
        tool="performance",
        operation="iostat",
        permission_class=_pc("iostat"),
        complexity="diagnostic",
        user_input="after the backup finished disk is still busy — run iostat to confirm it has settled",
        notes="Diagnostic: post-backup I/O verification.",
    ),

    # =========================================================================
    # vmstat  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="performance-vmstat-0001",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="single",
        user_input="show me virtual memory stats",
        notes="Single vmstat sample — quick memory and swap check.",
    ),
    Scenario(
        id="performance-vmstat-0002",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="single",
        user_input="run vmstat with 3 samples at 1-second intervals",
        notes="Short vmstat observation period.",
    ),
    Scenario(
        id="performance-vmstat-0003",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="diagnostic",
        user_input="the host is swapping heavily — run vmstat to see memory pressure",
        notes="Diagnostic: vmstat to investigate swap activity.",
    ),
    Scenario(
        id="performance-vmstat-0004",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="multi",
        user_input="collect 5 vmstat samples and tell me if swap usage is non-zero",
        notes="Multi-step: vmstat collection followed by swap-usage evaluation.",
    ),
    Scenario(
        id="performance-vmstat-0005",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="diagnostic",
        user_input="the OOM killer fired last night — pull vmstat to see what memory looks like now",
        notes="Diagnostic: post-OOM memory state investigation.",
    ),
    Scenario(
        id="performance-vmstat-0006",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="single",
        user_input="check if this host has free memory available",
        notes="Single vmstat to gauge available free memory.",
    ),
    Scenario(
        id="performance-vmstat-0007",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("vmstat"),
        complexity="multi",
        user_input="run vmstat every 2 seconds for 6 seconds and flag if context switches are above 5000/s",
        notes="Multi-step: observe context switch rate over time.",
    ),

    # =========================================================================
    # mpstat  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="performance-mpstat-0001",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="single",
        user_input="show per-CPU utilization",
        notes="Single mpstat snapshot for a multi-core host.",
    ),
    Scenario(
        id="performance-mpstat-0002",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="single",
        user_input="collect 3 mpstat samples at 1-second intervals",
        notes="Short mpstat run to observe CPU load distribution.",
    ),
    Scenario(
        id="performance-mpstat-0003",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="diagnostic",
        user_input="one CPU core is at 100% — use mpstat to find which one",
        notes="Diagnostic: per-CPU breakdown to identify a pinned core.",
    ),
    Scenario(
        id="performance-mpstat-0004",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="multi",
        user_input="run mpstat and check if any individual CPU has %iowait above 20%",
        notes="Multi-step: per-CPU iowait check.",
    ),
    Scenario(
        id="performance-mpstat-0005",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="diagnostic",
        user_input="after pinning a process to a single CPU the system is unresponsive — show mpstat so I can confirm the affinity is correct",
        notes="Diagnostic: CPU affinity verification via mpstat.",
    ),
    Scenario(
        id="performance-mpstat-0006",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="single",
        user_input="take a quick per-CPU snapshot with mpstat",
        notes="One-shot mpstat reading.",
    ),
    Scenario(
        id="performance-mpstat-0007",
        tool="performance",
        operation="mpstat",
        permission_class=_pc("mpstat"),
        complexity="multi",
        user_input="collect 5 mpstat samples and tell me the average %usr across all CPUs",
        notes="Multi-step: collect and aggregate per-CPU %usr.",
    ),

    # =========================================================================
    # uptime  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="performance-uptime-0001",
        tool="performance",
        operation="uptime",
        permission_class=_pc("uptime"),
        complexity="single",
        user_input="how long has this server been running?",
        notes="Basic uptime query — first thing to check after an alert.",
    ),
    Scenario(
        id="performance-uptime-0002",
        tool="performance",
        operation="uptime",
        permission_class=_pc("uptime"),
        complexity="single",
        user_input="show me the load average",
        notes="uptime for current load averages.",
    ),
    Scenario(
        id="performance-uptime-0003",
        tool="performance",
        operation="uptime",
        permission_class=_pc("uptime"),
        complexity="diagnostic",
        user_input="the server was restarted unexpectedly — confirm the uptime so I know when it came back",
        notes="Diagnostic: verify reboot time via uptime after an unexpected restart.",
    ),
    Scenario(
        id="performance-uptime-0004",
        tool="performance",
        operation="uptime",
        permission_class=_pc("uptime"),
        complexity="multi",
        user_input="check the uptime and load average, then tell me if the 1-minute load is above 4.0",
        notes="Multi-step: uptime then threshold evaluation.",
    ),
    Scenario(
        id="performance-uptime-0005",
        tool="performance",
        operation="uptime",
        permission_class=_pc("uptime"),
        complexity="diagnostic",
        user_input="the host is not responding to pings — if it's back up, check the uptime to see if it just rebooted",
        notes="Diagnostic: confirm reboot following a connectivity event.",
    ),

    # =========================================================================
    # load  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="performance-load-0001",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="single",
        user_input="what is the current system load?",
        notes="Quick load average read from /proc/loadavg.",
    ),
    Scenario(
        id="performance-load-0002",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="single",
        user_input="show the 1-minute, 5-minute, and 15-minute load averages",
        notes="Explicit three-window load average request.",
    ),
    Scenario(
        id="performance-load-0003",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="diagnostic",
        user_input="the monitoring system triggered a high-load alert — check /proc/loadavg to confirm",
        notes="Diagnostic: confirm high-load alert by reading /proc/loadavg directly.",
    ),
    Scenario(
        id="performance-load-0004",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="multi",
        user_input="read the load averages and tell me if the 15-minute load is above the number of CPUs",
        notes="Multi-step: load check followed by CPU-count comparison.",
    ),
    Scenario(
        id="performance-load-0005",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="diagnostic",
        user_input="the deployment just finished — check the load average to see if it has settled",
        notes="Diagnostic: post-deployment load verification.",
    ),
    Scenario(
        id="performance-load-0006",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="single",
        user_input="read /proc/loadavg",
        notes="Direct /proc/loadavg read — admin shorthand.",
    ),
    Scenario(
        id="performance-load-0007",
        tool="performance",
        operation="load",
        permission_class=_pc("load"),
        complexity="multi",
        user_input="check the load average and, if the 1-minute load is above 10, also pull sar CPU stats",
        notes="Multi-step: conditional escalation from load check to sar.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("performance").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "performance", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("performance").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
