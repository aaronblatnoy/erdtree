"""finetune/scenarios/systemd_timers.py — Scenario corpus for the 'systemd_timers' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list-timers   READ   — list all timer units and their trigger times
  timer-show    READ   — show properties of a specific timer unit
  create        WRITE  — install a timer unit file and reload systemd
  enable        WRITE  — enable a timer unit at boot
  disable       WRITE  — disable a timer unit from starting at boot
  systemd-run   WRITE  — schedule a one-shot transient command

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
    """Return the live permission class for a systemd_timers operation."""
    return registry.get("systemd_timers").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list-timers  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-list-timers-0001",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="single",
        user_input="show me all the scheduled timers on this system",
        notes="Basic read: list all systemd timers and their schedules.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0002",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="single",
        user_input="what timers are currently active?",
        notes="Operator wants a quick overview of running timers.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0003",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="diagnostic",
        user_input="something is running every hour and filling the disk — list all timers so I can figure out what it is",
        notes="Diagnostic: identify an unknown recurring job via the timer list.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0004",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="single",
        user_input="list all timers including inactive ones",
        notes="Read: include inactive timers in the listing.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0005",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="multi",
        user_input="show all timers and tell me which ones haven't run in the last 7 days",
        notes="Multi-step: list timers then interpret the LAST column for stale timers.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0006",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="diagnostic",
        user_input="the logrotate job isn't rotating logs — check if the logrotate timer is scheduled",
        notes="Diagnostic: verify the logrotate.timer is present and scheduled.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0007",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="single",
        user_input="when is the next dnf-makecache timer going to run?",
        notes="Read: operator wants the NEXT trigger time for a specific well-known timer.",
    ),
    Scenario(
        id="systemd_timers-list-timers-0008",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("list-timers"),
        complexity="multi",
        user_input="list the timers and check if the fstrim timer is enabled on this SSD host",
        notes="Multi-step: list timers and confirm fstrim.timer presence for SSD trim.",
    ),

    # =========================================================================
    # timer-show  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-timer-show-0001",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="single",
        user_input="show me the details of the backup.timer unit",
        notes="Read: display all properties of the backup timer.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0002",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="single",
        user_input="what is the schedule for logrotate.timer?",
        notes="Read: check the calendar spec for the logrotate timer.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0003",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="diagnostic",
        user_input="the dnf-makecache timer fired at 3am and caused a CPU spike — show its properties",
        notes="Diagnostic: inspect timer configuration to understand its schedule and triggered service.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0004",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="single",
        user_input="show details for the fstrim.timer",
        notes="Read: inspect the weekly fstrim timer properties.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0005",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="multi",
        user_input="show the properties of db-backup.timer and tell me which service it triggers",
        notes="Multi-step: show timer properties then identify the associated .service unit.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0006",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="single",
        user_input="what is the current state of the audit-report.timer?",
        notes="Read: check whether the audit report timer is active or waiting.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0007",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="diagnostic",
        user_input="the cert-renewal timer should have run yesterday but the cert is expired — show its properties",
        notes="Diagnostic: inspect cert-renewal.timer to find the last trigger time and result.",
    ),
    Scenario(
        id="systemd_timers-timer-show-0008",
        tool="systemd_timers",
        operation="timer-show",
        permission_class=_pc("timer-show"),
        complexity="single",
        user_input="check the properties of the cleanup.timer unit we deployed last week",
        notes="Read: verify a recently deployed custom timer's configuration.",
    ),

    # =========================================================================
    # create  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-create-0001",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="create a daily backup timer that runs at 2am",
        notes="WRITE: install a new backup.timer unit file and reload systemd.",
    ),
    Scenario(
        id="systemd_timers-create-0002",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="install a weekly log-archive timer that runs every Sunday at midnight",
        notes="WRITE: create log-archive.timer with a weekly OnCalendar spec.",
    ),
    Scenario(
        id="systemd_timers-create-0003",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="multi",
        user_input="create a cert-renewal timer that fires monthly then enable it and start it",
        notes="Multi-step: create timer unit, then enable, then start it.",
    ),
    Scenario(
        id="systemd_timers-create-0004",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="write a systemd timer unit for the db-vacuum job that runs every night at 3am",
        notes="WRITE: create db-vacuum.timer with OnCalendar=*-*-* 03:00:00.",
    ),
    Scenario(
        id="systemd_timers-create-0005",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="diagnostic",
        user_input="the audit-report script has no schedule — create a weekly timer for it",
        notes="Diagnostic-triggered WRITE: an unscheduled script needs a timer unit.",
    ),
    Scenario(
        id="systemd_timers-create-0006",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="create a timer to run the health-check service every 15 minutes",
        notes="WRITE: create health-check.timer with OnCalendar=*:0/15.",
    ),
    Scenario(
        id="systemd_timers-create-0007",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="multi",
        user_input="install a cleanup.timer that purges temp files daily and then show me the timer properties to confirm",
        notes="Multi-step: create timer then verify with timer-show.",
    ),
    Scenario(
        id="systemd_timers-create-0008",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="set up a nightly rsync-offsite timer that runs at 1am",
        notes="WRITE: create rsync-offsite.timer for offsite backup scheduling.",
    ),

    # =========================================================================
    # enable  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-enable-0001",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the backup.timer so it runs at boot",
        notes="WRITE: enable backup timer to persist across reboots.",
    ),
    Scenario(
        id="systemd_timers-enable-0002",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="make the logrotate.timer start automatically",
        notes="WRITE: ensure logrotate timer is enabled at boot.",
    ),
    Scenario(
        id="systemd_timers-enable-0003",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable the cert-renewal timer and then confirm it is enabled",
        notes="Multi-step: enable timer then verify via timer-show.",
    ),
    Scenario(
        id="systemd_timers-enable-0004",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable db-vacuum.timer on this database host",
        notes="WRITE: enable a database maintenance timer.",
    ),
    Scenario(
        id="systemd_timers-enable-0005",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="diagnostic",
        user_input="the health-check timer isn't running after the last reboot — enable it",
        notes="Diagnostic-triggered WRITE: timer was not enabled and didn't survive a reboot.",
    ),
    Scenario(
        id="systemd_timers-enable-0006",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the fstrim.timer for this SSD host",
        notes="WRITE: enable weekly SSD trim timer — standard hardening step.",
    ),
    Scenario(
        id="systemd_timers-enable-0007",
        tool="systemd_timers",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable the cleanup.timer and list all timers so I can see it in the schedule",
        notes="Multi-step: enable timer then list all timers to confirm it appears.",
    ),

    # =========================================================================
    # disable  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-disable-0001",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the backup.timer — we are moving to a different backup solution",
        notes="WRITE: disable a timer that is no longer needed.",
    ),
    Scenario(
        id="systemd_timers-disable-0002",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="stop the dnf-makecache timer from running — it causes I/O spikes",
        notes="WRITE: disable the dnf cache refresh timer to reduce I/O load.",
    ),
    Scenario(
        id="systemd_timers-disable-0003",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="multi",
        user_input="disable the old-cleanup.timer and confirm it is no longer in the enabled list",
        notes="Multi-step: disable timer then list timers to confirm removal.",
    ),
    Scenario(
        id="systemd_timers-disable-0004",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="diagnostic",
        user_input="the db-vacuum timer is running during peak hours and slowing the database — disable it",
        notes="Diagnostic-triggered WRITE: emergency disable of a timer causing performance issues.",
    ),
    Scenario(
        id="systemd_timers-disable-0005",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the audit-report.timer on this decommissioned host",
        notes="WRITE: disable timers as part of host decommission.",
    ),
    Scenario(
        id="systemd_timers-disable-0006",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="turn off the cert-renewal.timer while the PKI is being replaced",
        notes="WRITE: temporarily disable cert renewal during a PKI migration.",
    ),
    Scenario(
        id="systemd_timers-disable-0007",
        tool="systemd_timers",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="multi",
        user_input="disable the health-check.timer and show me the timer list to confirm it is gone",
        notes="Multi-step: disable then verify the timer is no longer scheduled.",
    ),

    # =========================================================================
    # systemd-run  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="systemd_timers-systemd-run-0001",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="single",
        user_input="run a one-shot backup script right now via systemd",
        notes="WRITE: use systemd-run to execute a script as a transient unit.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0002",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="single",
        user_input="schedule a one-time disk cleanup to run in 30 seconds using systemd-run",
        notes="WRITE: transient one-shot job with a short delay via --on-active.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0003",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="multi",
        user_input="use systemd-run to trigger the db-vacuum script now and then check the journal for its output",
        notes="Multi-step: systemd-run transient job then pull journal for results.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0004",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="single",
        user_input="run /usr/local/bin/cert-renew.sh once right now as a transient systemd unit",
        notes="WRITE: one-shot cert renewal script execution via systemd-run.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0005",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="diagnostic",
        user_input="the backup didn't run last night — trigger it manually now via systemd-run so we don't miss the window",
        notes="Diagnostic-triggered WRITE: manual trigger of a missed scheduled job.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0006",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="single",
        user_input="schedule /usr/sbin/aide --check to run once in 5 minutes using systemd-run",
        notes="WRITE: transient AIDE integrity check scheduled via systemd-run.",
    ),
    Scenario(
        id="systemd_timers-systemd-run-0007",
        tool="systemd_timers",
        operation="systemd-run",
        permission_class=_pc("systemd-run"),
        complexity="multi",
        user_input="use systemd-run to run the log-archive script now and confirm it exits successfully",
        notes="Multi-step: run transient job then check its exit status via journal.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("systemd_timers").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "systemd_timers", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("systemd_timers").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
