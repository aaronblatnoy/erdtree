"""finetune/scenarios/at.py — Scenario corpus for the 'at' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  atq       READ        — list pending at jobs in the queue
  schedule  WRITE       — schedule a one-off command to run at a given time
  atrm      DESTRUCTIVE — remove a queued at job by job number (irreversible)

Coverage targets
----------------
  >= 40 entries total across all 3 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the confirm-before-execute gate.

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
    """Return the live permission class for an at operation."""
    return registry.get("at").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # atq  (READ) — 14 entries
    # =========================================================================

    Scenario(
        id="at-atq-0001",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="show me the pending at jobs",
        notes="Basic atq list — operator checking the job queue.",
    ),
    Scenario(
        id="at-atq-0002",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="list all scheduled at jobs",
        notes="Synonym phrasing for atq.",
    ),
    Scenario(
        id="at-atq-0003",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="what jobs are queued in at?",
        notes="Question-form read request.",
    ),
    Scenario(
        id="at-atq-0004",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="check if there are any pending one-time jobs",
        notes="Operator verifying queue is empty before maintenance.",
    ),
    Scenario(
        id="at-atq-0005",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="show the at job queue for queue b",
        notes="Filtered atq with queue letter b.",
    ),
    Scenario(
        id="at-atq-0006",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="multi",
        user_input="list all at jobs and tell me which ones are due in the next hour",
        notes="Multi-step: list then filter by time — operator triaging upcoming work.",
    ),
    Scenario(
        id="at-atq-0007",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="diagnostic",
        user_input="a script that was supposed to run tonight hasn't fired — show me what's in the at queue",
        notes="Diagnostic: inspect queue to see if the job is still pending or was removed.",
    ),
    Scenario(
        id="at-atq-0008",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="how many at jobs are waiting to run?",
        notes="Count-oriented atq read.",
    ),
    Scenario(
        id="at-atq-0009",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="diagnostic",
        user_input="I need to audit what deferred commands are pending on this server before the change window",
        notes="Pre-change-window audit of the at queue.",
    ),
    Scenario(
        id="at-atq-0010",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="multi",
        user_input="list the at queue and show me the job numbers so I can decide which ones to cancel",
        notes="Multi-step: list then prepare for selective atrm.",
    ),
    Scenario(
        id="at-atq-0011",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="display all deferred tasks scheduled with at",
        notes="Alternate wording for atq with all jobs.",
    ),
    Scenario(
        id="at-atq-0012",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="diagnostic",
        user_input="the database cleanup was supposed to run at midnight but the tables still look full — is the job still in the queue?",
        notes="Diagnostic: check whether a specific job fired or is still waiting.",
    ),
    Scenario(
        id="at-atq-0013",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="single",
        user_input="check the at spool for any jobs",
        notes="spool-oriented phrasing for atq.",
    ),
    Scenario(
        id="at-atq-0014",
        tool="at",
        operation="atq",
        permission_class=_pc("atq"),
        complexity="multi",
        user_input="list the at queue and then remove any jobs older than job 5",
        notes="Multi-step: read queue then conditionally remove stale jobs.",
    ),

    # =========================================================================
    # schedule  (WRITE) — 16 entries
    # =========================================================================

    Scenario(
        id="at-schedule-0001",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="schedule a disk usage report to run at midnight tonight",
        notes="WRITE: schedule a read-only reporting command at midnight.",
    ),
    Scenario(
        id="at-schedule-0002",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="run the backup script at 2am tomorrow",
        notes="WRITE: schedule a backup command for tomorrow.",
    ),
    Scenario(
        id="at-schedule-0003",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="schedule a restart of the application service in 30 minutes",
        notes="WRITE: deferred service restart via at.",
    ),
    Scenario(
        id="at-schedule-0004",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="run the log rotation script at noon",
        notes="WRITE: schedule a log rotation task at noon.",
    ),
    Scenario(
        id="at-schedule-0005",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="multi",
        user_input="schedule a report generation at 11pm and then verify the job was queued",
        notes="Multi-step: schedule then check atq to confirm.",
    ),
    Scenario(
        id="at-schedule-0006",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="queue a one-time job to clear /tmp at 3am",
        notes="WRITE: deferred cleanup job via at.",
    ),
    Scenario(
        id="at-schedule-0007",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="diagnostic",
        user_input="the deployment needs to happen after business hours — schedule it for 9pm",
        notes="Diagnostic-triggered WRITE: schedule deployment outside business hours.",
    ),
    Scenario(
        id="at-schedule-0008",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="schedule a dnf update at midnight next Sunday",
        notes="WRITE: deferred package update via at.",
    ),
    Scenario(
        id="at-schedule-0009",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="run the health check script now + 2 hours",
        notes="WRITE: schedule health check using relative time.",
    ),
    Scenario(
        id="at-schedule-0010",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="multi",
        user_input="schedule the certificate renewal script for tomorrow at 6am and list the at queue to confirm",
        notes="Multi-step: schedule then atq to verify the job was accepted.",
    ),
    Scenario(
        id="at-schedule-0011",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="deferred-run the database vacuum at 1am",
        notes="WRITE: schedule a database maintenance task via at.",
    ),
    Scenario(
        id="at-schedule-0012",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="diagnostic",
        user_input="the archive job failed earlier — reschedule it for tonight at 11:30pm",
        notes="Diagnostic-triggered WRITE: re-queue a previously failed job.",
    ),
    Scenario(
        id="at-schedule-0013",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="schedule a script to notify the on-call team at 6am if the disk is above 90%",
        notes="WRITE: conditional monitoring notification via at.",
    ),
    Scenario(
        id="at-schedule-0014",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="run the weekly report generator at teatime Friday",
        notes="WRITE: using the at 'teatime' keyword alias.",
    ),
    Scenario(
        id="at-schedule-0015",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="multi",
        user_input="schedule a reboot for the staging server at 4am and confirm the job was accepted",
        notes="Multi-step: schedule then check queue — deferred reboot via at.",
    ),
    Scenario(
        id="at-schedule-0016",
        tool="at",
        operation="schedule",
        permission_class=_pc("schedule"),
        complexity="single",
        user_input="queue a one-time task to send a disk report by email at noon tomorrow",
        notes="WRITE: email notification job via at.",
    ),

    # =========================================================================
    # atrm  (DESTRUCTIVE) — 14 entries
    # =========================================================================

    Scenario(
        id="at-atrm-0001",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="cancel at job number 7",
        notes="DESTRUCTIVE: remove a specific queued at job.",
    ),
    Scenario(
        id="at-atrm-0002",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="delete at job 3 from the queue",
        notes="DESTRUCTIVE: remove job 3 — irreversible cancellation.",
    ),
    Scenario(
        id="at-atrm-0003",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="remove the at job that was scheduled to run at midnight",
        notes="DESTRUCTIVE: cancel a deferred job by identifying its number first.",
    ),
    Scenario(
        id="at-atrm-0004",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="multi",
        user_input="list all at jobs then remove job 5",
        notes="Multi-step DESTRUCTIVE: read queue first, then cancel a specific job.",
    ),
    Scenario(
        id="at-atrm-0005",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="diagnostic",
        user_input="the deployment was accidentally scheduled — cancel at job 12 immediately",
        notes="Diagnostic-triggered DESTRUCTIVE: emergency cancellation of a mis-scheduled job.",
    ),
    Scenario(
        id="at-atrm-0006",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="abort at job 2 before it runs",
        notes="DESTRUCTIVE: cancel a job before its scheduled execution time.",
    ),
    Scenario(
        id="at-atrm-0007",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="remove the midnight backup job from the at queue",
        notes="DESTRUCTIVE: cancel a backup that is no longer needed.",
    ),
    Scenario(
        id="at-atrm-0008",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="multi",
        user_input="show all pending at jobs and cancel any that are for job ids above 10",
        notes="Multi-step DESTRUCTIVE: inspect then bulk-cancel by criteria.",
    ),
    Scenario(
        id="at-atrm-0009",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="diagnostic",
        user_input="a stale cleanup job from last week is still in the at queue — remove it",
        notes="Diagnostic-triggered DESTRUCTIVE: remove a stale queued job.",
    ),
    Scenario(
        id="at-atrm-0010",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="cancel job 1 in the at spool",
        notes="DESTRUCTIVE: remove job 1 — simplest cancellation form.",
    ),
    Scenario(
        id="at-atrm-0011",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="I want to stop at job 9 from running",
        notes="DESTRUCTIVE: operator canceling a job before its time fires.",
    ),
    Scenario(
        id="at-atrm-0012",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="multi",
        user_input="check the at queue and remove the reboot job if it is still there",
        notes="Multi-step DESTRUCTIVE: conditional removal after reading the queue.",
    ),
    Scenario(
        id="at-atrm-0013",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="diagnostic",
        user_input="the maintenance window was pushed back — remove job 4 and reschedule it for 4am",
        notes="Diagnostic workflow: cancel then reschedule — DESTRUCTIVE + WRITE sequence.",
    ),
    Scenario(
        id="at-atrm-0014",
        tool="at",
        operation="atrm",
        permission_class=_pc("atrm"),
        complexity="single",
        user_input="purge at job 6 from the queue",
        notes="DESTRUCTIVE: remove job 6 — alternate verb for job removal.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("at").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "at", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("at").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
