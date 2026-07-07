"""core/tools/audit.py — Linux audit subsystem management via auditctl/ausearch/aureport/auditd.

Supported operations
--------------------
  list          (READ)        — list active audit rules via auditctl -l.
  status        (READ)        — show audit subsystem status via auditctl -s.
  add-rule      (WRITE)       — add an audit rule via auditctl -a.
  delete-rule   (DESTRUCTIVE) — delete an audit rule or all rules via auditctl -d / -D.
  search-by-comm (READ)       — search audit log by executable name via ausearch -c.
  search-by-key  (READ)       — search audit log by rule key via ausearch -k.
  search-by-time (READ)       — search audit log by time window via ausearch -ts.
  report         (READ)       — generate summary report via aureport.
  auditd-start   (WRITE)      — start the audit daemon via systemctl start auditd.
  auditd-stop    (WRITE)      — stop the audit daemon via systemctl stop auditd.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection (verbatim from services.py)
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """auditctl -l — list active audit rules."""
    result = run_subprocess(["auditctl", "-l"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        rule_count = result.stdout.count("\n")
        summary = f"Listed {rule_count} active audit rule(s)."
    else:
        summary = f"Failed to list audit rules (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_status(args: dict[str, Any]) -> ToolResult:
    """auditctl -s — show audit subsystem status."""
    result = run_subprocess(["auditctl", "-s"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Audit subsystem status retrieved."
    else:
        summary = f"Failed to retrieve audit status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add_rule(args: dict[str, Any]) -> ToolResult:
    """auditctl -a <rule> — add an audit rule.

    The `rule` argument is the complete rule specification passed to -a,
    e.g. 'always,exit -F arch=b64 -S execve -k exec_watch'.
    """
    rule: str = args["rule"]
    rule_parts = rule.split()
    cmd = ["auditctl", "-a"] + rule_parts
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Audit rule added: {rule!r}."
    else:
        summary = f"Failed to add audit rule {rule!r} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_delete_rule(args: dict[str, Any]) -> ToolResult:
    """auditctl -d <rule> or auditctl -D — delete one rule or all rules.

    If `rule` is provided, removes that specific rule with -d.
    If `rule` is absent or empty, deletes ALL rules with -D (DESTRUCTIVE).
    """
    rule: str = args.get("rule", "") or ""
    if rule.strip():
        rule_parts = rule.strip().split()
        cmd = ["auditctl", "-d"] + rule_parts
        summary_target = f"rule {rule!r}"
    else:
        cmd = ["auditctl", "-D"]
        summary_target = "all audit rules"
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Deleted {summary_target}."
    else:
        summary = f"Failed to delete {summary_target} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_search_by_comm(args: dict[str, Any]) -> ToolResult:
    """ausearch -c <comm> — search the audit log by executable name."""
    comm: str = args["comm"]
    result = run_subprocess(["ausearch", "-c", comm])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        event_count = result.stdout.count("----")
        summary = f"Found {event_count} audit event(s) for executable '{comm}'."
    else:
        summary = f"Audit search by executable '{comm}' returned no results or failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_search_by_key(args: dict[str, Any]) -> ToolResult:
    """ausearch -k <key> — search the audit log by rule key."""
    key: str = args["key"]
    result = run_subprocess(["ausearch", "-k", key])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        event_count = result.stdout.count("----")
        summary = f"Found {event_count} audit event(s) matching key '{key}'."
    else:
        summary = f"Audit search by key '{key}' returned no results or failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_search_by_time(args: dict[str, Any]) -> ToolResult:
    """ausearch -ts <start> [-te <end>] — search the audit log by time window."""
    start: str = args["start"]
    end: str = args.get("end", "") or ""
    cmd = ["ausearch", "-ts", start]
    if end.strip():
        cmd += ["-te", end.strip()]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        event_count = result.stdout.count("----")
        time_desc = f"from '{start}'" + (f" to '{end}'" if end.strip() else "")
        summary = f"Found {event_count} audit event(s) {time_desc}."
    else:
        summary = f"Audit time-range search from '{start}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_report(args: dict[str, Any]) -> ToolResult:
    """aureport [--summary | --file | --login | ...] — generate an audit summary report."""
    report_type: str = args.get("report_type", "") or ""
    if report_type.strip():
        cmd = ["aureport", f"--{report_type.strip()}"]
    else:
        cmd = ["aureport", "--summary"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    label = report_type.strip() if report_type.strip() else "summary"
    if result.ok:
        summary = f"Audit {label} report generated."
    else:
        summary = f"Failed to generate audit {label} report (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_auditd_start(args: dict[str, Any]) -> ToolResult:
    """systemctl start auditd — start the audit daemon."""
    result = run_subprocess(["systemctl", "start", "auditd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Audit daemon started."
    else:
        summary = f"Failed to start audit daemon (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_auditd_stop(args: dict[str, Any]) -> ToolResult:
    """systemctl stop auditd — stop the audit daemon.

    Note: stopping the audit daemon halts all kernel audit logging.
    """
    result = run_subprocess(["systemctl", "stop", "auditd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Audit daemon stopped; kernel audit logging is now inactive."
    else:
        summary = f"Failed to stop audit daemon (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list":            _op_list,
    "status":          _op_status,
    "add-rule":        _op_add_rule,
    "delete-rule":     _op_delete_rule,
    "search-by-comm":  _op_search_by_comm,
    "search-by-key":   _op_search_by_key,
    "search-by-time":  _op_search_by_time,
    "report":          _op_report,
    "auditd-start":    _op_auditd_start,
    "auditd-stop":     _op_auditd_stop,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an audit operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never writes to the audit log (I4) and never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for audit tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

AUDIT_SPEC = ToolSpec(
    name="audit",
    description="Manage the Linux audit subsystem via auditctl, ausearch, aureport, and auditd.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List the currently active kernel audit rules.",
        ),
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the audit subsystem.",
        ),
        "add-rule": OpSpec(
            op_name="add-rule",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="rule",
                    type=str,
                    required=True,
                    description=(
                        "Full auditctl rule specification passed to -a, "
                        "e.g. 'always,exit -F arch=b64 -S execve -k exec_watch'."
                    ),
                ),
            ],
            description="Add a kernel audit rule via auditctl -a.",
        ),
        "delete-rule": OpSpec(
            op_name="delete-rule",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="rule",
                    type=str,
                    required=False,
                    description=(
                        "Rule specification to remove with auditctl -d. "
                        "If absent, all rules are deleted with auditctl -D."
                    ),
                    default=None,
                ),
            ],
            description="Delete a specific audit rule (-d) or all rules (-D). DESTRUCTIVE.",
        ),
        "search-by-comm": OpSpec(
            op_name="search-by-comm",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="comm",
                    type=str,
                    required=True,
                    description="Executable name to search for in the audit log (ausearch -c).",
                ),
            ],
            description="Search the audit log for events matching an executable name.",
        ),
        "search-by-key": OpSpec(
            op_name="search-by-key",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="key",
                    type=str,
                    required=True,
                    description="Audit rule key to search for in the audit log (ausearch -k).",
                ),
            ],
            description="Search the audit log for events matching a rule key.",
        ),
        "search-by-time": OpSpec(
            op_name="search-by-time",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="start",
                    type=str,
                    required=True,
                    description=(
                        "Start time for the search window (ausearch -ts). "
                        "Accepts 'recent', 'today', 'yesterday', or 'MM/DD/YYYY HH:MM:SS'."
                    ),
                ),
                ArgSpec(
                    name="end",
                    type=str,
                    required=False,
                    description="End time for the search window (ausearch -te). Defaults to now.",
                    default=None,
                ),
            ],
            description="Search the audit log for events within a time window.",
        ),
        "report": OpSpec(
            op_name="report",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="report_type",
                    type=str,
                    required=False,
                    description=(
                        "Report type passed to aureport: 'summary', 'file', 'login', "
                        "'auth', 'avc', 'exec'. Defaults to 'summary'."
                    ),
                    default=None,
                ),
            ],
            description="Generate an audit summary or detailed report via aureport.",
        ),
        "auditd-start": OpSpec(
            op_name="auditd-start",
            permission_class=OpClass.WRITE,
            args=[],
            description="Start the audit daemon via systemctl start auditd.",
        ),
        "auditd-stop": OpSpec(
            op_name="auditd-stop",
            permission_class=OpClass.WRITE,
            args=[],
            description="Stop the audit daemon via systemctl stop auditd. Halts kernel audit logging.",
        ),
    },
    execute=_execute,
)

# Self-registration at import (last line).
registry.register(AUDIT_SPEC)
