"""finetune/scenarios/processes.py — Scenario corpus for the 'processes' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list    READ   — list all running processes (ps aux)
  tree    READ   — show process hierarchy (ps -ejH / pstree)
  top     READ   — snapshot CPU/memory-sorted process list
  info    READ   — detailed info for a single PID
  signal  WRITE  — send a signal to a PID (kill)
  renice  WRITE  — change scheduling priority of a PID (renice)

Coverage targets
----------------
  >= 60 entries total across all 6 operations.
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
    """Return the live permission class for a processes operation."""
    return registry.get("processes").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="processes-list-0001",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all running processes",
        notes="Basic process listing — most common operator request.",
    ),
    Scenario(
        id="processes-list-0002",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what processes are currently running on this host?",
        notes="Equivalent phrasing for a full process snapshot.",
    ),
    Scenario(
        id="processes-list-0003",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list every process on the system right now",
        notes="Operator wants a complete snapshot before a maintenance window.",
    ),
    Scenario(
        id="processes-list-0004",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="get a full process list and flag anything that looks like a Java process",
        notes="Multi-step: list processes then filter for Java workloads.",
    ),
    Scenario(
        id="processes-list-0005",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show all processes and tell me which ones are owned by the postgres user",
        notes="Multi-step: list then filter by user ownership.",
    ),
    Scenario(
        id="processes-list-0006",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the host is sluggish — get me a full process list so we can see what is running",
        notes="Diagnostic: first-pass snapshot during a performance incident.",
    ),
    Scenario(
        id="processes-list-0007",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="something is chewing through memory — list all processes so I can identify the culprit",
        notes="Diagnostic: memory pressure investigation starting point.",
    ),
    Scenario(
        id="processes-list-0008",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="can you pull the full process table for me?",
        notes="Conversational phrasing for ps aux.",
    ),
    Scenario(
        id="processes-list-0009",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all running processes and count how many are in a zombie state",
        notes="Multi-step: list then count zombie-state entries.",
    ),
    Scenario(
        id="processes-list-0010",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I suspect an unauthorized process is running — dump the full process list for review",
        notes="Security-hardening diagnostic: scan for unexpected processes.",
    ),
    Scenario(
        id="processes-list-0011",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show running processes on this box",
        notes="Short imperative form — common in interactive sessions.",
    ),
    Scenario(
        id="processes-list-0012",
        tool="processes",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="before I reboot, list all active processes so I know what will be interrupted",
        notes="Pre-maintenance process audit to avoid surprise service interruption.",
    ),

    # =========================================================================
    # tree  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="processes-tree-0001",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="single",
        user_input="show me the process tree",
        notes="Basic process hierarchy view.",
    ),
    Scenario(
        id="processes-tree-0002",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="single",
        user_input="display the process hierarchy on this host",
        notes="Alternate phrasing for a process tree snapshot.",
    ),
    Scenario(
        id="processes-tree-0003",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="single",
        user_input="give me a tree view of all running processes",
        notes="Operator wants to see parent-child relationships.",
    ),
    Scenario(
        id="processes-tree-0004",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="multi",
        user_input="show the process tree and identify any processes that forked unexpectedly from systemd",
        notes="Multi-step: tree then analyse for unexpected systemd children.",
    ),
    Scenario(
        id="processes-tree-0005",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="diagnostic",
        user_input="I see a mystery process — show the process tree so I can trace its parent",
        notes="Diagnostic: use tree to find the parent of an unknown process.",
    ),
    Scenario(
        id="processes-tree-0006",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="diagnostic",
        user_input="something is spawning dozens of child processes — get the process tree so I can see what is happening",
        notes="Diagnostic: fork-bomb or runaway subprocess detection via tree.",
    ),
    Scenario(
        id="processes-tree-0007",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="single",
        user_input="show process parentage — who spawned what",
        notes="Operator wants a top-down hierarchy for capacity planning.",
    ),
    Scenario(
        id="processes-tree-0008",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="multi",
        user_input="print the process tree and tell me how deep the deepest chain of children goes",
        notes="Multi-step: tree then calculate maximum depth.",
    ),
    Scenario(
        id="processes-tree-0009",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="diagnostic",
        user_input="nginx is spawning too many workers — check the process tree to confirm",
        notes="Diagnostic: verify worker count via tree before taking action.",
    ),
    Scenario(
        id="processes-tree-0010",
        tool="processes",
        operation="tree",
        permission_class=_pc("tree"),
        complexity="single",
        user_input="what does the process hierarchy look like right now?",
        notes="General process tree inquiry during a routine health check.",
    ),

    # =========================================================================
    # top  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="processes-top-0001",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="what processes are using the most CPU right now?",
        notes="Classic CPU top-consumers request.",
    ),
    Scenario(
        id="processes-top-0002",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="give me a snapshot of the top processes by CPU usage",
        notes="Explicit top-by-CPU request.",
    ),
    Scenario(
        id="processes-top-0003",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="which process is pegging the CPU?",
        notes="High-CPU alert — operator wants to know the culprit.",
    ),
    Scenario(
        id="processes-top-0004",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="the server is at 100% CPU — snapshot the top processes immediately",
        notes="Diagnostic: CPU saturation incident, urgent process snapshot.",
    ),
    Scenario(
        id="processes-top-0005",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="load average is spiking — what processes are driving the CPU?",
        notes="Diagnostic: correlate load average spike with specific processes.",
    ),
    Scenario(
        id="processes-top-0006",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="multi",
        user_input="get a CPU snapshot and tell me if any single process is above 50% CPU",
        notes="Multi-step: snapshot then check for runaway single-process consumption.",
    ),
    Scenario(
        id="processes-top-0007",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="multi",
        user_input="show me top processes by CPU and let me know which user is running the heaviest one",
        notes="Multi-step: top snapshot then extract the owning user.",
    ),
    Scenario(
        id="processes-top-0008",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="take a quick process snapshot sorted by resource usage",
        notes="General performance check — CPU-sorted snapshot.",
    ),
    Scenario(
        id="processes-top-0009",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="diagnostic",
        user_input="users are complaining of slowness — take a CPU snapshot and see what is hogging resources",
        notes="Diagnostic: user-reported performance degradation, CPU snapshot first step.",
    ),
    Scenario(
        id="processes-top-0010",
        tool="processes",
        operation="top",
        permission_class=_pc("top"),
        complexity="single",
        user_input="show current CPU hogs",
        notes="Terse operator shorthand for a CPU-sorted process snapshot.",
    ),

    # =========================================================================
    # info  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="processes-info-0001",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me detailed info for PID 1234",
        notes="Direct PID detail request.",
    ),
    Scenario(
        id="processes-info-0002",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what is process 5678 doing?",
        notes="Conversational PID inquiry — operator wants full detail.",
    ),
    Scenario(
        id="processes-info-0003",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="get me the full ps output for PID 9012",
        notes="Explicit request for the ps -p detail record.",
    ),
    Scenario(
        id="processes-info-0004",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="look up PID 3344 and tell me who owns it and how much CPU it is using",
        notes="Multi-step: info then extract owner and CPU fields.",
    ),
    Scenario(
        id="processes-info-0005",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="I see PID 7777 in the process list consuming memory — tell me everything about it",
        notes="Diagnostic: deep dive on a suspicious high-memory process.",
    ),
    Scenario(
        id="processes-info-0006",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="before I send a signal to PID 4321, show me what that process is so I do not kill the wrong thing",
        notes="Diagnostic: confirm process identity before acting — safety check.",
    ),
    Scenario(
        id="processes-info-0007",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="get the stat and command line for process 1001",
        notes="Operator wants stat field and full argv string.",
    ),
    Scenario(
        id="processes-info-0008",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what is the parent PID of process 2048?",
        notes="Parentage lookup — common in process-tree analysis.",
    ),
    Scenario(
        id="processes-info-0009",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="look up PID 6600 and confirm whether it is running as root",
        notes="Multi-step: info then check if user field is root — security concern.",
    ),
    Scenario(
        id="processes-info-0010",
        tool="processes",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="PID 8888 appeared after the last deployment — show me its full details so I can understand what it is",
        notes="Post-deployment process audit — verify new process is expected.",
    ),

    # =========================================================================
    # signal  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="processes-signal-0001",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="send SIGTERM to PID 1234 to shut it down gracefully",
        notes="Graceful termination — most common signal scenario.",
    ),
    Scenario(
        id="processes-signal-0002",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="kill process 5678 with SIGKILL — it is not responding to SIGTERM",
        notes="Force-kill after graceful shutdown failed.",
    ),
    Scenario(
        id="processes-signal-0003",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="send signal 15 to PID 9999 to request a clean shutdown",
        notes="SIGTERM by number — same intent as scenario 0001, different phrasing.",
    ),
    Scenario(
        id="processes-signal-0004",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="tell PID 2048 to reload its configuration with SIGHUP",
        notes="SIGHUP config-reload pattern — common for daemons.",
    ),
    Scenario(
        id="processes-signal-0005",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="multi",
        user_input="look up what PID 3300 is running, then terminate it with SIGTERM if it is a stale worker",
        notes="Multi-step: info first, then conditional signal — confirm before act.",
    ),
    Scenario(
        id="processes-signal-0006",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="diagnostic",
        user_input="the PHP-FPM worker at PID 4400 is stuck in D state — try sending it SIGTERM and check if it clears",
        notes="Diagnostic: attempt graceful signal on a stuck process, observe result.",
    ),
    Scenario(
        id="processes-signal-0007",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="force kill PID 7070 — it has been zombie for an hour",
        notes="SIGKILL on a long-running zombie process.",
    ),
    Scenario(
        id="processes-signal-0008",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="diagnostic",
        user_input="the batch job at PID 5500 is consuming 95% CPU and has been for 30 minutes — send it a SIGTERM",
        notes="Diagnostic-driven signal: high-CPU runaway job termination.",
    ),
    Scenario(
        id="processes-signal-0009",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="multi",
        user_input="check what is running as PID 6601, then if it is not a core service send signal 9 to kill it",
        notes="Multi-step: verify identity first, then signal — safety gate pattern.",
    ),
    Scenario(
        id="processes-signal-0010",
        tool="processes",
        operation="signal",
        permission_class=_pc("signal"),
        complexity="single",
        user_input="send SIGUSR1 to PID 1100 to trigger a log rotation",
        notes="Application-specific signal for log rotation — common for daemons like nginx.",
    ),

    # =========================================================================
    # renice  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="processes-renice-0001",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="single",
        user_input="lower the priority of PID 3300 to nice value 10 so it does not starve other work",
        notes="Reduce priority of a background job to free up CPU for foreground workloads.",
    ),
    Scenario(
        id="processes-renice-0002",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="single",
        user_input="set the scheduling priority of PID 7777 to nice 15",
        notes="Explicit nice-value assignment for a low-priority batch task.",
    ),
    Scenario(
        id="processes-renice-0003",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="single",
        user_input="renice PID 4400 to -5 to give it higher CPU priority",
        notes="Raise priority (negative nice) for a latency-sensitive process.",
    ),
    Scenario(
        id="processes-renice-0004",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="multi",
        user_input="check what PID 8800 is before bumping its nice value to 19 to deprioritize it",
        notes="Multi-step: info check then renice — confirm identity before changing scheduling.",
    ),
    Scenario(
        id="processes-renice-0005",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="diagnostic",
        user_input="the nightly backup at PID 2200 is slowing down the database — renice it to 10 to reduce its CPU share",
        notes="Diagnostic-driven renice: backup job interfering with production workload.",
    ),
    Scenario(
        id="processes-renice-0006",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="single",
        user_input="deprioritize the compression job at PID 5500 by setting its nice value to 19",
        notes="Maximum deprioritization for a background compression task.",
    ),
    Scenario(
        id="processes-renice-0007",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="diagnostic",
        user_input="the reporting pipeline at PID 6601 is competing with the web tier for CPU — lower its nice to 15 and see if response times improve",
        notes="Performance tuning: renice a batch process to relieve pressure on the web tier.",
    ),
    Scenario(
        id="processes-renice-0008",
        tool="processes",
        operation="renice",
        permission_class=_pc("renice"),
        complexity="multi",
        user_input="take a CPU snapshot, identify the background process with the highest CPU, then renice it to 10",
        notes="Multi-step: snapshot to find top consumer, then renice to ease load.",
    ),
]
