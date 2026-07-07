"""finetune/simulate/audit.py — Rocky Linux 9 output simulator for the 'audit' tool.

Public API
----------
simulate_audit(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 10 real operations declared in core/tools/audit.py
    args : dict of op arguments (may be {} for all-optional ops; defaults applied per-op)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms supported via isinstance checks (mirrors services.py pattern).

Realism model
-------------
* Exit codes mirror real auditctl / ausearch / aureport / systemctl behaviour on Rocky 9.
* stdout/stderr reflect actual tool output formats.
* Failure branches are deterministic: 'notfound', 'broken', 'fail', 'missing', 'bogus'
  tokens in the key/comm trigger failure; hash-based scatter adds variety.
* auditd-start/stop delegate to the systemctl interface.

I2 compliance
-------------
All `summary` strings are I2-clean. No AI/LLM/model/agent/agentic/neural/
language model text appears in any returned string.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (circular-dep avoidance).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _auditd_is_running(ctx: Any) -> bool:
    """Return True if the audit daemon appears to be running in ctx."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("auditd" in s for s in active)
    if isinstance(ctx, str):
        return "auditd" in ctx
    return True  # default: assume running (typical hardened Rocky 9)


def _bad_key(key: str) -> bool:
    """Return True for deterministically bad/missing keys."""
    lower = key.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % 25 == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate auditctl -l."""
    if not _auditd_is_running(ctx):
        stderr = "auditctl: Cannot contact Audit Daemon\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to list audit rules; the audit subsystem is not reachable.",
        )
    stdout = (
        "-a always,exit -F arch=b64 -S execve -k exec_watch\n"
        "-a always,exit -F arch=b64 -S open -F exit=-EACCES -k access_denied\n"
        "-a always,exit -F arch=b64 -S unlink -S unlinkat -k delete_watch\n"
        "-w /etc/passwd -p wa -k identity\n"
        "-w /etc/shadow -p wa -k identity\n"
        "-w /etc/sudoers -p wa -k sudoers\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Listed 6 active audit rule(s).",
    )


def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate auditctl -s."""
    if not _auditd_is_running(ctx):
        stderr = "auditctl: Cannot contact Audit Daemon\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to retrieve audit status; the audit daemon is not running.",
        )
    stdout = (
        "enabled 1\n"
        "failure 1\n"
        "pid 1234\n"
        "rate_limit 0\n"
        "backlog_limit 8192\n"
        "lost 0\n"
        "backlog 0\n"
        "backlog_wait_time 60000\n"
        "loginuid_immutable 0 unlocked\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Audit subsystem status retrieved.",
    )


def _sim_add_rule(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate auditctl -a <rule>."""
    rule = args.get("rule", "")
    if not rule.strip():
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="auditctl: Invalid rule syntax\n",
            summary="Failed to add audit rule: the rule specification is empty.",
        )
    # Detect obviously broken rules
    if "broken" in rule.lower() or "invalid" in rule.lower():
        stderr = "auditctl: Error sending add rule data request (Invalid argument)\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add audit rule {rule!r}; the rule syntax was rejected.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Audit rule added: {rule!r}.",
    )


def _sim_delete_rule(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate auditctl -d <rule> or auditctl -D."""
    rule = args.get("rule", "") or ""
    if rule.strip():
        # Delete specific rule
        if "broken" in rule.lower() or "notfound" in rule.lower():
            stderr = "auditctl: Error sending delete rule data request (No such file or directory)\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"Failed to delete audit rule {rule!r}; the rule was not found.",
            )
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"Deleted audit rule {rule!r}.",
        )
    else:
        # Delete ALL rules (-D)
        if not _auditd_is_running(ctx):
            stderr = "auditctl: Cannot contact Audit Daemon\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary="Failed to delete all audit rules; the audit daemon is not reachable.",
            )
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Deleted all audit rules.",
        )


def _sim_search_by_comm(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate ausearch -c <comm>."""
    comm = args.get("comm", "unknown")
    host = _hostname(ctx)
    if _bad_key(comm):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="<no events of interest were found>\n",
            summary=f"Audit search by executable '{comm}' returned no results.",
        )
    ts = "1751500000.123"
    stdout = (
        f"----\n"
        f"time->Fri Jul  4 00:00:00 2026\n"
        f"type=SYSCALL msg=audit({ts}:1001): arch=c000003e syscall=59 success=yes "
        f"exit=0 a0=7f2a1b2c3d40 a1=7ffdb1a2c3d0 a2=7ffdb1a2c3e0 a3=0 "
        f"items=2 ppid=5432 pid=7891 auid=1000 uid=0 gid=0 euid=0 suid=0 "
        f"fsuid=0 egid=0 sgid=0 fsgid=0 tty=pts0 ses=3 comm=\"{comm}\" "
        f"exe=\"/usr/bin/{comm}\" subj=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023 "
        f"key=\"exec_watch\"\n"
        f"type=CWD msg=audit({ts}:1001): cwd=\"/root\"\n"
        f"type=PATH msg=audit({ts}:1001): item=0 name=\"/usr/bin/{comm}\" "
        f"inode=123456 dev=fd:01 mode=0100755 ouid=0 ogid=0 rdev=00:00 "
        f"obj=system_u:object_r:bin_t:s0 objtype=NORMAL cap_fp=0 cap_fi=0 "
        f"cap_fe=0 cap_fver=0 cap_frootid=0\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found 1 audit event(s) for executable '{comm}'.",
    )


def _sim_search_by_key(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate ausearch -k <key>."""
    key = args.get("key", "unknown")
    host = _hostname(ctx)
    if _bad_key(key):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="<no events of interest were found>\n",
            summary=f"Audit search by key '{key}' returned no results.",
        )
    ts1 = "1751500100.456"
    ts2 = "1751500200.789"
    stdout = (
        f"----\n"
        f"time->Fri Jul  4 00:01:40 2026\n"
        f"type=SYSCALL msg=audit({ts1}:1042): arch=c000003e syscall=2 success=yes "
        f"exit=3 a0=7f1a2b3c4d50 a1=0 a2=1b6 a3=24 items=1 ppid=1 pid=3301 "
        f"auid=0 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 "
        f"tty=(none) ses=4294967295 comm=\"crond\" exe=\"/usr/sbin/crond\" "
        f"subj=system_u:system_r:crond_t:s0-s0:c0.c1023 key=\"{key}\"\n"
        f"----\n"
        f"time->Fri Jul  4 00:03:20 2026\n"
        f"type=SYSCALL msg=audit({ts2}:1063): arch=c000003e syscall=2 success=yes "
        f"exit=4 a0=7f3c4d5e6f70 a1=0 a2=1b6 a3=24 items=1 ppid=1 pid=3302 "
        f"auid=0 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 "
        f"tty=(none) ses=4294967295 comm=\"sshd\" exe=\"/usr/sbin/sshd\" "
        f"subj=system_u:system_r:sshd_t:s0-s0:c0.c1023 key=\"{key}\"\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found 2 audit event(s) matching key '{key}'.",
    )


def _sim_search_by_time(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate ausearch -ts <start> [-te <end>]."""
    start = args.get("start", "recent")
    end = args.get("end", "") or ""

    if "broken" in start.lower() or "invalid" in start.lower():
        stderr = f"ausearch: Unknown time format: {start}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Audit time-range search from '{start}' failed; the time format was not recognised.",
        )

    time_desc = f"from '{start}'" + (f" to '{end}'" if end.strip() else "")
    ts = "1751503600.001"
    stdout = (
        f"----\n"
        f"time->Fri Jul  4 01:00:00 2026\n"
        f"type=LOGIN msg=audit({ts}:2001): pid=8765 uid=0 subj=system_u:system_r:sshd_t:s0-s0:c0.c1023 "
        f"old-auid=4294967295 auid=1001 tty=(none) old-ses=4294967295 ses=12 res=1\n"
        f"----\n"
        f"time->Fri Jul  4 01:00:01 2026\n"
        f"type=SYSCALL msg=audit(1751503601.002:2002): arch=c000003e syscall=59 success=yes "
        f"exit=0 a0=0 a1=0 a2=0 a3=0 items=2 ppid=8765 pid=8766 "
        f"auid=1001 uid=1001 gid=1001 euid=1001 suid=1001 fsuid=1001 egid=1001 sgid=1001 fsgid=1001 "
        f"tty=pts1 ses=12 comm=\"bash\" exe=\"/bin/bash\" "
        f"subj=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023 key=(null)\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found 2 audit event(s) {time_desc}.",
    )


def _sim_report(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate aureport [--summary | ...]."""
    report_type = (args.get("report_type", "") or "").strip()
    label = report_type if report_type else "summary"

    if not _auditd_is_running(ctx):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="aureport: Error opening config file (No such file or directory)\n",
            summary=f"Failed to generate audit {label} report; the audit log is not accessible.",
        )

    if report_type in ("", "summary"):
        stdout = (
            "\nSummary Report\n"
            "======================\n"
            "Range of time in logs: 07/03/2026 00:00:01.000 - 07/04/2026 09:59:59.000\n"
            "Selected time for report: 07/03/2026 00:00:01 - 07/04/2026 09:59:59.000\n"
            "Number of changes in configuration: 4\n"
            "Number of changes to accounts, groups, or roles: 2\n"
            "Number of logins: 17\n"
            "Number of failed logins: 3\n"
            "Number of authentications: 21\n"
            "Number of failed authentications: 3\n"
            "Number of users: 3\n"
            "Number of terminals: 5\n"
            "Number of host names: 4\n"
            "Number of executables: 29\n"
            "Number of commands: 45\n"
            "Number of files: 71\n"
            "Number of AVC's: 0\n"
            "Number of MAC events: 0\n"
            "Number of failed syscalls: 12\n"
            "Number of anomaly events: 0\n"
            "Number of responses to anomaly events: 0\n"
            "Number of crypto events: 8\n"
            "Number of integrity events: 0\n"
            "Number of virt events: 0\n"
            "Number of keys: 6\n"
            "Number of process IDs: 128\n"
            "Number of events: 1542\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Audit summary report generated.",
        )
    elif report_type == "file":
        stdout = (
            "File Report\n"
            "===============================================\n"
            "# date time file syscall success exe auid event\n"
            "===============================================\n"
            "1. 07/04/2026 00:00:02 /etc/passwd 2 yes /usr/bin/cat 1000 1001\n"
            "2. 07/04/2026 00:01:15 /etc/shadow 2 yes /usr/bin/id 0 1002\n"
            "3. 07/04/2026 00:05:33 /etc/sudoers 2 yes /usr/bin/sudo 1000 1003\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Audit file report generated.",
        )
    elif report_type == "login":
        stdout = (
            "Login Report\n"
            "=====================================================\n"
            "# date time auid host term exe success event\n"
            "=====================================================\n"
            "1. 07/04/2026 00:00:01 1000 192.168.1.100 ssh /usr/sbin/sshd yes 2001\n"
            "2. 07/04/2026 01:30:44 1001 192.168.1.105 ssh /usr/sbin/sshd yes 2002\n"
            "3. 07/04/2026 03:12:55 500 10.0.0.22 ssh /usr/sbin/sshd no 2003\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Audit login report generated.",
        )
    elif report_type == "avc":
        stdout = (
            "AVC Report\n"
            "===============================================\n"
            "# date time comm subj obj class perm event\n"
            "===============================================\n"
            "No AVC events found in the log range.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Audit AVC report generated.",
        )
    else:
        # Unknown report type — aureport exits non-zero
        stderr = f"aureport: Unknown report type: --{report_type}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to generate audit {label} report; the report type was not recognised.",
        )


def _sim_auditd_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate systemctl start auditd."""
    if _auditd_is_running(ctx):
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Audit daemon was already running; start command completed without error.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Audit daemon started.",
    )


def _sim_auditd_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate systemctl stop auditd."""
    if not _auditd_is_running(ctx):
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Audit daemon was already stopped; stop command completed without error.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Audit daemon stopped; kernel audit logging is now inactive.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":            _sim_list,
    "status":          _sim_status,
    "add-rule":        _sim_add_rule,
    "delete-rule":     _sim_delete_rule,
    "search-by-comm":  _sim_search_by_comm,
    "search-by-key":   _sim_search_by_key,
    "search-by-time":  _sim_search_by_time,
    "report":          _sim_report,
    "auditd-start":    _sim_auditd_start,
    "auditd-stop":     _sim_auditd_stop,
}


def simulate_audit(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'audit' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 10 real ops declared in
           core/tools/audit.py (list, status, add-rule, delete-rule,
           search-by-comm, search-by-key, search-by-time, report,
           auditd-start, auditd-stop).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict
           with 'active_services' / 'hostname' keys.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_audit: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
