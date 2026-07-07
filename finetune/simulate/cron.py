"""finetune/simulate/cron.py — Rocky Linux 9 output simulator for the 'cron' tool.

Public API
----------
simulate_cron(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/cron.py
           (list, list-all, edit, remove, crond-view, crond-add)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'hostname' key.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real crontab / tee / ls / cat behaviour on Rocky Linux 9:
    0  — success
    1  — operation failed (permission denied, syntax error, etc.)
* list: shows realistic crontab entries with comments
* list-all: shows /var/spool/cron/ directory listing
* edit: no stdout (crontab - is silent on success)
* remove: no stdout (crontab -r is silent on success)
* crond-view: either ls output or cat of a cron.d file
* crond-add: tee echoes content to stdout on success
* Failure triggers are deterministic via hash-based scatter and keyword
  matching (missing/bogus/notfound/fail tokens trigger failure branches).

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic/neural).

INV-read-only-core: imports NOTHING from core/ directly.
Does NOT import finetune.coreimports (avoids circular deps at Phase-13 init).
The 4-key dict mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _should_fail(key: str) -> bool:
    """Deterministically decide if a key should trigger a failure response.

    Triggers: the token 'notfound', 'bogus', 'missing', 'fail', 'noexist', or
    'bad' appears in the lowercase key; OR a hash-based 15% scatter adds variety.
    """
    lower = key.lower()
    for tok in ("notfound", "bogus", "missing", "fail", "noexist", "bad", "invalid"):
        if tok in lower:
            return True
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % 20 == 0


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


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate crontab -l [-u user]."""
    user: str | None = args.get("user")
    target_key = user if user else "currentuser"
    target_label = f"user '{user}'" if user else "current user"

    if user and _should_fail(user):
        stderr = f"crontab: user '{user}' does not exist\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to list crontab: user '{user}' was not found.",
        )

    # Check if the user has no crontab
    h = int(hashlib.md5(target_key.encode()).hexdigest(), 16)
    if h % 7 == 1:
        stderr = f"no crontab for {user or 'root'}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"No crontab entries found for {target_label}.",
        )

    stdout = (
        "# Crontab for {}\n"
        "# Edit this file to introduce tasks to be run by cron.\n"
        "#\n"
        "# m h  dom mon dow   command\n"
        "0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1\n"
        "15 4 * * 0 /usr/bin/find /tmp -mtime +7 -delete\n"
        "*/5 * * * * /usr/local/bin/healthcheck.sh\n"
        "30 6 1 * * /usr/local/sbin/monthly-report.sh\n"
    ).format(user or "root")
    line_count = stdout.count("\n")
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Crontab for {target_label} listed ({line_count} lines).",
    )


def _sim_list_all(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate ls -la /var/spool/cron/ — list all user crontab files."""
    stdout = (
        "total 24\n"
        "drwx--x--x. 2 root root  60 Jul 01 08:00 .\n"
        "drwxr-xr-x. 7 root root 140 Jun 15 12:00 ..\n"
        "-rw-------. 1 root root 215 Jul 01 08:00 deploy\n"
        "-rw-------. 1 root root 183 Jun 28 14:22 postgres\n"
        "-rw-------. 1 root root 142 Jun 30 09:11 root\n"
    )
    entries = [
        ln for ln in stdout.splitlines()
        if ln.strip() and not ln.startswith("total")
        and not ln.endswith((" .", " .."))
    ]
    count = len(entries)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {count} crontab file(s) in /var/spool/cron/.",
    )


def _sim_edit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate crontab - [-u user] — replace crontab from stdin."""
    content: str = args.get("content", "")
    user: str | None = args.get("user")
    target_label = f"user '{user}'" if user else "current user"

    if user and _should_fail(user):
        stderr = f"crontab: user '{user}' does not exist\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to update crontab: user '{user}' was not found.",
        )

    # Check for syntax errors in content (very simplified check)
    if content and "INVALID" in content.upper():
        stderr = "crontab: installing new crontab\n/tmp/crontab.XXXXXX:1: bad minute\nerrors in crontab file, can't install\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Crontab syntax error; crontab for {target_label} was not updated.",
        )

    # crontab - is silent on success
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Crontab for {target_label} updated successfully.",
    )


def _sim_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate crontab -r [-u user] — remove an entire crontab."""
    user: str | None = args.get("user")
    target_label = f"user '{user}'" if user else "current user"

    if user and _should_fail(user):
        stderr = f"crontab: user '{user}' does not exist\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove crontab: user '{user}' was not found.",
        )

    # crontab -r is silent on success — no stdout, no stderr
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Crontab for {target_label} removed (all scheduled jobs deleted).",
    )


def _sim_crond_view(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate cat /etc/cron.d/<name> or ls -la /etc/cron.d/."""
    name: str | None = args.get("name")

    if name:
        if _should_fail(name):
            stderr = f"cat: /etc/cron.d/{name}: No such file or directory\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"Failed to read /etc/cron.d/{name}: file not found.",
            )
        # Realistic cron.d file content
        stdout = (
            f"# /etc/cron.d/{name} — drop-in cron job\n"
            f"SHELL=/bin/bash\n"
            f"PATH=/sbin:/bin:/usr/sbin:/usr/bin\n"
            f"MAILTO=root\n"
            f"\n"
            f"# Run the {name} task daily at 3 AM\n"
            f"0 3 * * * root /usr/local/bin/{name}.sh >> /var/log/{name}.log 2>&1\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Contents of /etc/cron.d/{name} retrieved.",
        )
    else:
        # List the directory
        stdout = (
            "total 40\n"
            "drwxr-xr-x.  2 root root  120 Jul 01 09:00 .\n"
            "drwxr-xr-x. 80 root root 8192 Jul 01 09:00 ..\n"
            "-rw-r--r--.  1 root root  128 Jun 15 00:00 0hourly\n"
            "-rw-r--r--.  1 root root  108 Jun 20 14:00 aide\n"
            "-rw-r--r--.  1 root root   93 Jun 22 09:15 backup-jobs\n"
            "-rw-r--r--.  1 root root  115 Jun 28 17:00 logrotate\n"
            "-rw-r--r--.  1 root root   87 Jun 30 08:00 sysstat\n"
        )
        entries = [
            ln for ln in stdout.splitlines()
            if ln.strip() and not ln.startswith("total")
            and not ln.endswith((" .", " .."))
        ]
        count = len(entries)
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Found {count} file(s) in /etc/cron.d/.",
        )


def _sim_crond_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate tee /etc/cron.d/<name> — write a cron.d drop-in file."""
    name: str = args.get("name", "")
    content: str = args.get("content", "")

    if not name or _should_fail(name):
        if not name:
            stderr = "tee: /etc/cron.d/: Is a directory\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary="Failed to write cron drop-in: no filename provided.",
            )
        stderr = f"tee: /etc/cron.d/{name}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to write /etc/cron.d/{name}: permission denied.",
        )

    # tee echoes the content to stdout
    return _make_result(
        exit_code=0,
        stdout=content,
        stderr="",
        summary=f"Cron drop-in file /etc/cron.d/{name} written successfully.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":       _sim_list,
    "list-all":   _sim_list_all,
    "edit":       _sim_edit,
    "remove":     _sim_remove,
    "crond-view": _sim_crond_view,
    "crond-add":  _sim_crond_add,
}


def simulate_cron(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'cron' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in
           core/tools/cron.py (list, list-all, edit, remove, crond-view, crond-add).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'hostname' key.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_cron: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
