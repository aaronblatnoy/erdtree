"""finetune/scenarios/audit.py — Scenario corpus for the 'audit' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list           READ        — list active kernel audit rules
  status         READ        — show audit subsystem status
  add-rule       WRITE       — add an audit rule via auditctl -a
  delete-rule    DESTRUCTIVE — delete a rule or all rules via auditctl -d / -D
  search-by-comm READ        — search audit log by executable name
  search-by-key  READ        — search audit log by rule key
  search-by-time READ        — search audit log by time window
  report         READ        — generate summary/detailed report via aureport
  auditd-start   WRITE       — start the audit daemon
  auditd-stop    WRITE       — stop the audit daemon

Coverage targets
----------------
  >= 40 entries total across all 10 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE and DESTRUCTIVE scenarios are honestly labeled (permission_class
  from live registry) so downstream traces teach the confirm-before-write gate.

INV-schema-sync: permission_class for each entry is derived from the LIVE
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
    """Return the live permission class for an audit operation."""
    return registry.get("audit").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="audit-list-0001",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all active audit rules",
        notes="Simple listing of the currently loaded kernel audit rule set.",
    ),
    Scenario(
        id="audit-list-0002",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what audit rules are currently in place on this system?",
        notes="Admin wants to review the active rule set before making changes.",
    ),
    Scenario(
        id="audit-list-0003",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all audit rules and tell me if any watch /etc/passwd",
        notes="Multi-step: list rules then filter output for identity-file watches.",
    ),
    Scenario(
        id="audit-list-0004",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="we need to verify our CIS benchmark audit rules are still loaded after the reboot",
        notes="Diagnostic: confirm audit rules survive a reboot — common compliance check.",
    ),
    Scenario(
        id="audit-list-0005",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the kernel audit rules so I can back them up",
        notes="Pre-change snapshot of the rule set.",
    ),
    Scenario(
        id="audit-list-0006",
        tool="audit",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the security scanner says audit rules are missing — show me what is loaded",
        notes="Diagnostic: reconcile scanner finding with live rule set.",
    ),

    # =========================================================================
    # status  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="audit-status-0001",
        tool="audit",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the current audit subsystem status",
        notes="Baseline audit status check.",
    ),
    Scenario(
        id="audit-status-0002",
        tool="audit",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is the kernel audit subsystem enabled?",
        notes="Quick check of the enabled flag in auditctl -s output.",
    ),
    Scenario(
        id="audit-status-0003",
        tool="audit",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="audit events seem to be getting dropped — check the audit backlog status",
        notes="Diagnostic: check backlog_limit and lost counters for audit event drops.",
    ),
    Scenario(
        id="audit-status-0004",
        tool="audit",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check audit status and then list the active rules to give me a full picture",
        notes="Multi-step: status followed by rule listing for full audit posture review.",
    ),
    Scenario(
        id="audit-status-0005",
        tool="audit",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the audit daemon PID and rate limit?",
        notes="Admin needs PID and rate_limit values from auditctl -s.",
    ),

    # =========================================================================
    # add-rule  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="audit-add-rule-0001",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="single",
        user_input="add an audit rule to watch all execve calls",
        notes="WRITE: add a syscall audit rule for execve monitoring.",
    ),
    Scenario(
        id="audit-add-rule-0002",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="single",
        user_input="audit all writes to /etc/passwd",
        notes="WRITE: add a file-watch rule for identity file changes.",
    ),
    Scenario(
        id="audit-add-rule-0003",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="single",
        user_input="add an audit rule to track changes to /etc/sudoers",
        notes="WRITE: privilege escalation file watch — common hardening step.",
    ),
    Scenario(
        id="audit-add-rule-0004",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="single",
        user_input="watch /etc/ssh/sshd_config for any modifications",
        notes="WRITE: SSH config change audit rule.",
    ),
    Scenario(
        id="audit-add-rule-0005",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="multi",
        user_input="add audit rules for all failed file access attempts and then verify they were loaded",
        notes="Multi-step: add EACCES/EPERM syscall rules then confirm with list.",
    ),
    Scenario(
        id="audit-add-rule-0006",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="single",
        user_input="add a rule to track privileged command use by non-root users",
        notes="WRITE: track setuid/setgid program execution — CIS benchmark requirement.",
    ),
    Scenario(
        id="audit-add-rule-0007",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("add-rule"),
        complexity="diagnostic",
        user_input="we suspect someone is deleting files — add an audit rule to catch unlink syscalls",
        notes="Diagnostic-triggered WRITE: add forensic rule to catch deletion activity.",
    ),

    # =========================================================================
    # delete-rule  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="audit-delete-rule-0001",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="single",
        user_input="remove all audit rules from the kernel",
        notes="DESTRUCTIVE: flush all audit rules with auditctl -D — used before re-loading a full rule set.",
    ),
    Scenario(
        id="audit-delete-rule-0002",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="single",
        user_input="delete the execve audit rule",
        notes="DESTRUCTIVE: remove a specific syscall watch rule.",
    ),
    Scenario(
        id="audit-delete-rule-0003",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="multi",
        user_input="clear all current audit rules and then load the new CIS-compliant rule set",
        notes="Multi-step DESTRUCTIVE: flush existing rules then add a fresh baseline.",
    ),
    Scenario(
        id="audit-delete-rule-0004",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="diagnostic",
        user_input="the audit subsystem is flooding syslog — remove the noisy exec watch rule",
        notes="Diagnostic-triggered DESTRUCTIVE: targeted removal of a high-volume rule.",
    ),
    Scenario(
        id="audit-delete-rule-0005",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="single",
        user_input="wipe all audit rules so I can start fresh",
        notes="DESTRUCTIVE: full rule flush before a clean reconfiguration.",
    ),
    Scenario(
        id="audit-delete-rule-0006",
        tool="audit",
        operation="delete-rule",
        permission_class=_pc("delete-rule"),
        complexity="single",
        user_input="delete the file watch rule on /etc/passwd",
        notes="DESTRUCTIVE: remove a specific file watch — must confirm before removing compliance rule.",
    ),

    # =========================================================================
    # search-by-comm  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="audit-search-by-comm-0001",
        tool="audit",
        operation="search-by-comm",
        permission_class=_pc("search-by-comm"),
        complexity="single",
        user_input="search the audit log for all sudo events",
        notes="Search for privilege escalation events by executable name.",
    ),
    Scenario(
        id="audit-search-by-comm-0002",
        tool="audit",
        operation="search-by-comm",
        permission_class=_pc("search-by-comm"),
        complexity="single",
        user_input="find all audit entries for sshd",
        notes="Search for SSH daemon activity in the audit log.",
    ),
    Scenario(
        id="audit-search-by-comm-0003",
        tool="audit",
        operation="search-by-comm",
        permission_class=_pc("search-by-comm"),
        complexity="diagnostic",
        user_input="we think someone ran useradd without authorization — find all useradd events in the audit log",
        notes="Diagnostic: forensic search for unauthorized account creation.",
    ),
    Scenario(
        id="audit-search-by-comm-0004",
        tool="audit",
        operation="search-by-comm",
        permission_class=_pc("search-by-comm"),
        complexity="multi",
        user_input="search the audit log for bash events and see if any came from unexpected users",
        notes="Multi-step: search by comm then analyze auid fields for anomalies.",
    ),
    Scenario(
        id="audit-search-by-comm-0005",
        tool="audit",
        operation="search-by-comm",
        permission_class=_pc("search-by-comm"),
        complexity="single",
        user_input="show audit events for the passwd command",
        notes="Search for password change events by executable.",
    ),

    # =========================================================================
    # search-by-key  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="audit-search-by-key-0001",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("search-by-key"),
        complexity="single",
        user_input="search the audit log for events tagged with key 'identity'",
        notes="Search for all identity-file change events by key.",
    ),
    Scenario(
        id="audit-search-by-key-0002",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("search-by-key"),
        complexity="single",
        user_input="find all audit entries with the 'sudoers' key",
        notes="Locate privilege escalation configuration change events.",
    ),
    Scenario(
        id="audit-search-by-key-0003",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("search-by-key"),
        complexity="diagnostic",
        user_input="pull all audit events tagged exec_watch to see what processes ran overnight",
        notes="Diagnostic: review execution events for a given time window via key search.",
    ),
    Scenario(
        id="audit-search-by-key-0004",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("search-by-key"),
        complexity="multi",
        user_input="search the audit log for 'delete_watch' key events and count how many files were deleted",
        notes="Multi-step: search by key then count events in the output.",
    ),
    Scenario(
        id="audit-search-by-key-0005",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("search-by-key"),
        complexity="single",
        user_input="show audit events matching the 'access_denied' key",
        notes="Find all failed file access attempts by rule key.",
    ),

    # =========================================================================
    # search-by-time  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="audit-search-by-time-0001",
        tool="audit",
        operation="search-by-time",
        permission_class=_pc("search-by-time"),
        complexity="single",
        user_input="show recent audit events",
        notes="Quick look at the most recent audit log entries.",
    ),
    Scenario(
        id="audit-search-by-time-0002",
        tool="audit",
        operation="search-by-time",
        permission_class=_pc("search-by-time"),
        complexity="single",
        user_input="pull all audit events from today",
        notes="Retrieve all events recorded today for a daily review.",
    ),
    Scenario(
        id="audit-search-by-time-0003",
        tool="audit",
        operation="search-by-time",
        permission_class=_pc("search-by-time"),
        complexity="diagnostic",
        user_input="the suspected intrusion happened between 2am and 4am last night — pull audit events for that window",
        notes="Diagnostic: targeted time-window search for forensic investigation.",
    ),
    Scenario(
        id="audit-search-by-time-0004",
        tool="audit",
        operation="search-by-time",
        permission_class=_pc("search-by-time"),
        complexity="multi",
        user_input="get all audit events from yesterday and look for any failed login attempts",
        notes="Multi-step: retrieve yesterday's audit events then filter for login failures.",
    ),
    Scenario(
        id="audit-search-by-time-0005",
        tool="audit",
        operation="search-by-time",
        permission_class=_pc("search-by-time"),
        complexity="single",
        user_input="show audit events from the last hour",
        notes="Recent event scan for ongoing monitoring.",
    ),

    # =========================================================================
    # report  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="audit-report-0001",
        tool="audit",
        operation="report",
        permission_class=_pc("report"),
        complexity="single",
        user_input="generate an audit summary report",
        notes="High-level overview of audit activity — common daily review task.",
    ),
    Scenario(
        id="audit-report-0002",
        tool="audit",
        operation="report",
        permission_class=_pc("report"),
        complexity="single",
        user_input="show me the audit file access report",
        notes="File-focused audit report for file integrity review.",
    ),
    Scenario(
        id="audit-report-0003",
        tool="audit",
        operation="report",
        permission_class=_pc("report"),
        complexity="diagnostic",
        user_input="we had a login anomaly last night — run the audit login report",
        notes="Diagnostic: review login events via aureport --login for incident response.",
    ),
    Scenario(
        id="audit-report-0004",
        tool="audit",
        operation="report",
        permission_class=_pc("report"),
        complexity="single",
        user_input="show me the AVC denial report from the audit log",
        notes="SELinux denial report — useful for policy troubleshooting.",
    ),
    Scenario(
        id="audit-report-0005",
        tool="audit",
        operation="report",
        permission_class=_pc("report"),
        complexity="multi",
        user_input="generate an audit summary report and highlight the failed syscall count",
        notes="Multi-step: generate summary then interpret the failed syscalls line.",
    ),

    # =========================================================================
    # auditd-start  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="audit-auditd-start-0001",
        tool="audit",
        operation="auditd-start",
        permission_class=_pc("auditd-start"),
        complexity="single",
        user_input="start the audit daemon",
        notes="WRITE: start auditd — post-install or post-maintenance startup.",
    ),
    Scenario(
        id="audit-auditd-start-0002",
        tool="audit",
        operation="auditd-start",
        permission_class=_pc("auditd-start"),
        complexity="multi",
        user_input="start auditd and then verify it is running",
        notes="Multi-step WRITE: start the daemon then confirm it is active.",
    ),
    Scenario(
        id="audit-auditd-start-0003",
        tool="audit",
        operation="auditd-start",
        permission_class=_pc("auditd-start"),
        complexity="diagnostic",
        user_input="the security compliance scan says auditd is not running — start it",
        notes="Diagnostic-triggered WRITE: remediate a compliance finding by starting auditd.",
    ),

    # =========================================================================
    # auditd-stop  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="audit-auditd-stop-0001",
        tool="audit",
        operation="auditd-stop",
        permission_class=_pc("auditd-stop"),
        complexity="single",
        user_input="stop the audit daemon for maintenance",
        notes="WRITE: graceful stop of auditd — halts kernel audit logging.",
    ),
    Scenario(
        id="audit-auditd-stop-0002",
        tool="audit",
        operation="auditd-stop",
        permission_class=_pc("auditd-stop"),
        complexity="multi",
        user_input="stop auditd, make the rule changes, then restart it",
        notes="Multi-step WRITE: stop daemon to make rule changes then restart.",
    ),
    Scenario(
        id="audit-auditd-stop-0003",
        tool="audit",
        operation="auditd-stop",
        permission_class=_pc("auditd-stop"),
        complexity="diagnostic",
        user_input="auditd is causing excessive disk I/O — stop it temporarily while we investigate",
        notes="Diagnostic-triggered WRITE: emergency stop of auditd to relieve I/O pressure.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("audit").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "audit", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("audit").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
