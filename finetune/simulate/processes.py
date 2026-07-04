"""finetune/simulate/processes.py — Rocky Linux 9 output simulator for the 'processes' tool.

Public API
----------
simulate_processes(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/processes.py
           (list, tree, top, info, signal, renice)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Both forms are supported.

Real ops and permission classes (from core/tools/processes.py PROCESSES_SPEC)
----------------------------------------------------------------------------
  list    READ   — ps aux; no required args
  tree    READ   — ps -ejH; no required args
  top     READ   — ps aux --sort=-%cpu; no required args
  info    READ   — ps -p <pid>; requires pid (int)
  signal  WRITE  — kill [-<signal_num>] <pid>; requires pid; signal_num optional
  renice  WRITE  — renice <priority> -p <pid>; requires pid and priority

Realism model
-------------
* All stdout/stderr reproduces authentic Rocky Linux 9 ps/kill/renice output.
* Failure triggers are keyed on argument values so the caller can produce both
  success and failure traces without extra configuration:
    pid == 99999         -> "No such process" failure for info/signal/renice
    pid == 1             -> permission denied for signal/renice (root-owned)
    signal_num == 9      -> SIGKILL success path (explicit coverage)
    signal_num == 0      -> probe/check path (exit 0, no actual kill)
    priority out of range -> clamped by the real tool (not an error here)
  When args is empty ({}) the simulator returns a SUCCESS result using safe
  defaults — the validation gate (simulate_processes(op, {}, ctx)) always passes.
* ctx is used to reflect running processes in list/tree/top output when it is
  a dict containing an "active_services" key (service names are mapped to
  plausible process names) or a str containing process hints.

I2 compliance
-------------
All `summary` strings are I2-clean.  assert_no_ai_language is NOT called inline
(to keep this module fast), but tests/finetune/test_i2.py asserts every summary.

INV-schema-sync   Op names are NEVER hardcoded outside the _DISPATCH table.
INV-read-only-core  This module imports FROM finetune.coreimports only.
INV-offline         No network calls, no subprocesses launched.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# I2 checker — always via coreimports (INV-I2, INV-read-only-core)
# ---------------------------------------------------------------------------
from finetune.coreimports import assert_no_ai_language  # noqa: F401 (used by test suite)

# ---------------------------------------------------------------------------
# Default placeholder values used when args keys are absent.
# ---------------------------------------------------------------------------
_DEFAULT_PID = 1234
_DEFAULT_PRIORITY = 5
_DEFAULT_SIGNAL = None  # None means SIGTERM (15) — the real tool default


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


def _active_services(ctx: Any) -> list[str]:
    """Return list of active service names from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("active_services", [])
    return []


def _pid_not_found(pid: int) -> bool:
    """Return True if the pid should simulate a 'No such process' error."""
    return pid == 99999 or pid <= 0


def _pid_permission_denied(pid: int) -> bool:
    """Return True if the pid should simulate a permission-denied error (root-owned)."""
    return pid == 1


# ---------------------------------------------------------------------------
# Realistic process table rows (used by list/tree/top)
# ---------------------------------------------------------------------------

_BASE_PROCESSES = [
    ("root",        "1",      "0.0",  "0.1",  "systemd",  "/usr/lib/systemd/systemd --switched-root --system --deserialize=30"),
    ("root",        "2",      "0.0",  "0.0",  "kthreadd", "[kthreadd]"),
    ("root",        "547",    "0.0",  "0.1",  "rsyslogd", "/usr/sbin/rsyslogd -n"),
    ("root",        "812",    "0.0",  "0.2",  "sshd",     "/usr/sbin/sshd -D"),
    ("root",        "904",    "0.0",  "0.1",  "crond",    "/usr/sbin/crond -n"),
    ("dbus",        "680",    "0.0",  "0.1",  "dbus-daemon", "/usr/bin/dbus-daemon --system"),
    ("polkitd",     "682",    "0.0",  "0.3",  "polkitd",  "/usr/lib/polkit-1/polkitd --no-debug"),
    ("root",        "1023",   "0.0",  "0.2",  "NetworkManager", "/usr/sbin/NetworkManager --no-daemon"),
    ("root",        "1105",   "0.0",  "0.1",  "auditd",   "/sbin/auditd"),
    ("root",        "1422",   "0.0",  "0.4",  "tuned",    "/usr/bin/python3 -Es /usr/sbin/tuned -l -P"),
    ("aaron",       "3210",   "0.1",  "0.5",  "bash",     "-bash"),
    ("aaron",       "3388",   "4.2",  "1.2",  "python3",  "python3 -m finetune.generate --n 600"),
    ("postfix",     "2100",   "0.0",  "0.1",  "master",   "/usr/libexec/postfix/master -w"),
    ("root",        "2350",   "0.0",  "0.3",  "firewalld", "/usr/bin/python3 -s /usr/sbin/firewalld --nofork"),
    ("chronyd",     "755",    "0.0",  "0.1",  "chronyd",  "/usr/sbin/chronyd"),
]


def _build_ps_header() -> str:
    return "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"


def _build_ps_row(user: str, pid: str, cpu: str, mem: str, comm: str, cmd: str) -> str:
    vsz = str(int(pid) * 41 % 900000 + 10000)
    rss = str(int(pid) * 17 % 80000 + 1000)
    return f"{user:<12} {pid:>6} {cpu:>4} {mem:>4} {vsz:>6} {rss:>6} ?        Ss   Jul02   0:00 {cmd}\n"


def _build_ps_rows(services: list[str], extra_rows: int = 0) -> str:
    rows = _build_ps_header()
    for user, pid, cpu, mem, comm, cmd in _BASE_PROCESSES:
        rows += _build_ps_row(user, pid, cpu, mem, comm, cmd)
    # Add rows for active services that aren't already in the base list
    known_comms = {r[4] for r in _BASE_PROCESSES}
    for svc in services:
        svc_base = svc.split(".")[0]
        if svc_base not in known_comms:
            pid_num = 1000 + (sum(ord(c) for c in svc) % 7000)
            rows += _build_ps_row(
                "root", str(pid_num), "0.0", "0.2",
                svc_base, f"/usr/sbin/{svc_base} -D"
            )
    return rows


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """ps aux — list all running processes."""
    services = _active_services(ctx)
    stdout = _build_ps_rows(services)
    line_count = stdout.count("\n") - 1  # subtract header
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {line_count} running processes.",
    )


def _sim_tree(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """ps -ejH — process tree with hierarchy indentation."""
    services = _active_services(ctx)
    header = "  PID  PGID   SID TTY          TIME CMD\n"
    rows = header
    rows += "    1     1     1 ?        00:00:03 systemd\n"
    rows += "  547   547   547 ?        00:00:00   rsyslogd\n"
    rows += "  812   812   812 ?        00:00:00   sshd\n"
    rows += "  904   904   904 ?        00:00:00   crond\n"
    rows += " 1023  1023  1023 ?        00:00:00   NetworkManager\n"
    rows += " 1105  1105  1105 ?        00:00:00   auditd\n"
    rows += " 2350  2350  2350 ?        00:00:01   firewalld\n"
    rows += " 3210  3210  3210 pts/0    00:00:00   bash\n"
    rows += " 3388  3210  3210 pts/0    00:00:04     python3\n"
    for svc in services:
        svc_base = svc.split(".")[0]
        pid_num = 1000 + (sum(ord(c) for c in svc) % 7000)
        rows += f"{pid_num:5d} {pid_num:5d} {pid_num:5d} ?        00:00:00   {svc_base}\n"
    line_count = rows.count("\n") - 1
    return _make_result(
        exit_code=0,
        stdout=rows,
        stderr="",
        summary=f"Process tree captured ({line_count} entries).",
    )


def _sim_top(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """ps aux --sort=-%cpu — processes sorted by CPU descending."""
    services = _active_services(ctx)
    # Build rows and sort by CPU (descending) — the high-CPU python3 row comes first
    rows = _build_ps_rows(services)
    # Split into header + data, sort data by CPU column (index 2)
    lines = rows.splitlines(keepends=True)
    header = lines[0]
    data = lines[1:]
    try:
        data_sorted = sorted(
            data,
            key=lambda l: float(l.split()[2]) if len(l.split()) > 2 else 0.0,
            reverse=True,
        )
    except Exception:
        data_sorted = data
    stdout = header + "".join(data_sorted)
    line_count = len(data_sorted)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Top {line_count} processes by CPU captured.",
    )


def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """ps -p <pid> -o pid,ppid,user,stat,pcpu,pmem,comm,args — single-PID detail."""
    pid = int(args.get("pid", _DEFAULT_PID))

    if _pid_not_found(pid):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: process ID out of range\n",
            summary=f"No process found for PID {pid}; it may have already exited.",
        )

    # Find this PID in the base table if it exists
    matched = None
    for user, base_pid, cpu, mem, comm, cmd in _BASE_PROCESSES:
        if int(base_pid) == pid:
            matched = (user, base_pid, cpu, mem, comm, cmd)
            break

    if matched:
        user, base_pid, cpu, mem, comm, cmd = matched
        ppid = "1" if comm not in ("bash", "python3") else "3210"
        stdout = (
            "  PID  PPID USER     STAT %CPU %MEM COMMAND         COMMAND\n"
            f"{pid:5d} {ppid:5s} {user:<8} Ss   {cpu:>4} {mem:>4} {comm:<15} {cmd}\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Process info for PID {pid} retrieved.",
        )

    # Generic plausible process
    stdout = (
        "  PID  PPID USER     STAT %CPU %MEM COMMAND         COMMAND\n"
        f"{pid:5d}     1 root     Ss    0.0  0.1 worker          /usr/bin/worker --pid-file /run/worker.pid\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Process info for PID {pid} retrieved.",
    )


def _sim_signal(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """kill [-<signal_num>] <pid> — send a signal to a process."""
    pid = int(args.get("pid", _DEFAULT_PID))
    signal_num = args.get("signal_num", _DEFAULT_SIGNAL)

    if _pid_not_found(pid):
        stderr = f"bash: kill: ({pid}) - No such process\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Signal to PID {pid} failed; no such process.",
        )

    if _pid_permission_denied(pid):
        stderr = f"bash: kill: ({pid}) - Operation not permitted\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Signal to PID {pid} was denied; insufficient privileges for that process.",
        )

    # signal_num == 0 is a probe (existence check) — always exits 0, no action
    if signal_num == 0:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"PID {pid} exists and is running (signal 0 probe succeeded).",
        )

    if signal_num is not None:
        sig_label = f"-{signal_num}" if signal_num > 0 else str(signal_num)
    else:
        sig_label = "TERM"

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Signal {sig_label} sent to PID {pid}.",
    )


def _sim_renice(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """renice <priority> -p <pid> — change process scheduling priority."""
    pid = int(args.get("pid", _DEFAULT_PID))
    priority = int(args.get("priority", _DEFAULT_PRIORITY))
    # Clamp to valid nice range [-20, 19]
    priority = max(-20, min(19, priority))

    if _pid_not_found(pid):
        stderr = f"renice: failed to set priority of process ID {pid}: No such process\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"renice for PID {pid} failed; no such process.",
        )

    if _pid_permission_denied(pid):
        stderr = f"renice: failed to set priority of process ID {pid}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"renice for PID {pid} was denied; insufficient privileges to adjust that process.",
        )

    stdout = f"{pid} (process ID) old priority 0, new priority {priority}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Priority of PID {pid} set to {priority}.",
    )


# ---------------------------------------------------------------------------
# Dispatch table — op names mirror PROCESSES_SPEC ops exactly (INV-schema-sync)
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list":   _sim_list,
    "tree":   _sim_tree,
    "top":    _sim_top,
    "info":   _sim_info,
    "signal": _sim_signal,
    "renice": _sim_renice,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def simulate_processes(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'processes' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in
           core/tools/processes.py PROCESSES_SPEC
           (list, tree, top, info, signal, renice).
    args : argument dict (may be sparse or empty; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with e.g. 'active_services' list.

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
            f"simulate_processes: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
