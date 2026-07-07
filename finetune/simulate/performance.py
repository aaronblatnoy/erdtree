"""finetune/simulate/performance.py — Rocky Linux 9 output simulator for the 'performance' tool.

Public API
----------
simulate_performance(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/performance.py
           (sar, iostat, vmstat, mpstat, uptime, load)
    args : dict of op arguments (may be {} for all-optional ops; defaults applied)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict. Both are supported via isinstance checks.

Realism model
-------------
* Output mirrors real Rocky Linux 9 sysstat/procps output formats.
* Failure branches trigger when a hash-based scatter fires, or when a
  sentinel value (interval=0, count=0, or negative) is detected.
* sysstat binaries (sar/iostat/mpstat) may legitimately be absent — their
  failure branch returns exit_code=127 with "command not found" text to
  teach error handling.
* All summaries are I2-clean.

INV-read-only-core: imports NOTHING from core/ or finetune.coreimports.
The ToolResult shape is mirrored as a plain dict.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky9.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky9"


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


def _sysstat_missing(tool_name: str) -> dict[str, Any]:
    """Return a realistic 'command not found' result for a sysstat binary."""
    stderr = f"bash: {tool_name}: command not found\n"
    return _make_result(
        exit_code=127,
        stdout="",
        stderr=stderr,
        summary=(
            f"{tool_name} is not installed. "
            "Install the sysstat package to enable this command."
        ),
    )


def _scatter_fail(key: str, modulus: int = 15) -> bool:
    """Deterministic hash-based scatter — True ~(1/modulus) of the time."""
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % modulus == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_sar(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    interval = int(args.get("interval", 1))
    count = int(args.get("count", 1))
    interval = max(1, interval)
    count = max(1, min(count, 60))
    host = _hostname(ctx)

    if _scatter_fail(f"sar-{host}"):
        return _sysstat_missing("sar")

    # Build realistic sar -u output
    header = (
        f"Linux 5.14.0-362.24.1.el9_3.x86_64 ({host})   "
        f"07/04/2026   _x86_64_   (4 CPU)\n\n"
    )
    col_header = (
        "12:00:00 AM     CPU     %user     %nice   %system   %iowait    %steal     %idle\n"
    )
    rows = []
    for i in range(count):
        hh = 12 + i
        row = (
            f"{hh:02d}:00:0{i} AM     all      2.{15+i:02d}      0.00      0.{45+i:02d}      "
            f"0.{i:02d}      0.00     97.{20-i:02d}\n"
        )
        rows.append(row)

    # Average line
    avg_row = (
        "\nAverage:        all      2.20      0.00      0.48      0.01      0.00     97.31\n"
    )
    stdout = header + col_header + "".join(rows) + avg_row

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"CPU utilization report collected ({count} sample(s) at {interval}s interval)."
        ),
    )


def _sim_iostat(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    interval = int(args.get("interval", 1))
    count = int(args.get("count", 1))
    interval = max(1, interval)
    count = max(1, min(count, 60))
    host = _hostname(ctx)

    if _scatter_fail(f"iostat-{host}"):
        return _sysstat_missing("iostat")

    header = (
        f"Linux 5.14.0-362.24.1.el9_3.x86_64 ({host})   "
        f"07/04/2026   _x86_64_   (4 CPU)\n\n"
    )
    cpu_block = (
        "avg-cpu:  %user   %nice %system %iowait  %steal   %idle\n"
        "           2.20    0.00    0.48    0.01    0.00   97.31\n\n"
    )
    dev_header = (
        "Device            r/s     rkB/s   rrqm/s  %rrqm r_await rareq-sz     "
        "w/s     wkB/s   wrqm/s  %wrqm w_await wareq-sz     d/s     dkB/s   drqm/s  "
        "%drqm d_await dareq-sz  aqu-sz  %util\n"
    )
    # Use profile's disk list or defaults
    disks = ["sda", "sdb"] if not isinstance(ctx, dict) else ctx.get("disks", ["sda"])
    dev_rows = ""
    for disk in disks:
        dev_rows += (
            f"{disk:<16}   12.34   512.00     0.50   3.90    0.82    41.49"
            f"    8.21   256.00     1.20  12.77    1.04    31.18"
            f"    0.00      0.00     0.00   0.00    0.00     0.00"
            f"    0.18    1.24\n"
        )

    stdout = header + cpu_block + dev_header + dev_rows

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Disk I/O statistics collected ({count} sample(s) at {interval}s interval)."
        ),
    )


def _sim_vmstat(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    interval = int(args.get("interval", 1))
    count = int(args.get("count", 1))
    interval = max(1, interval)
    count = max(1, min(count, 60))
    host = _hostname(ctx)

    if _scatter_fail(f"vmstat-{host}", modulus=20):
        stderr = "vmstat: error opening /proc/stat: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="vmstat failed to read /proc/stat (permission error).",
        )

    header = "procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----\n"
    col    = " r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st\n"
    rows = []
    for i in range(count):
        free_mb = 1024 * (8 - i % 4)
        rows.append(
            f" {i%3}  0      0 {free_mb * 1024:>6}  {2048 + i * 10:>6}  {512000 + i * 200:>7}"
            f"    0    0     2     8  {450+i:>4}  {820+i:>4}  2  1 97  0  0\n"
        )
    stdout = header + col + "".join(rows)

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Virtual memory statistics collected ({count} sample(s) at {interval}s interval)."
        ),
    )


def _sim_mpstat(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    interval = int(args.get("interval", 1))
    count = int(args.get("count", 1))
    interval = max(1, interval)
    count = max(1, min(count, 60))
    host = _hostname(ctx)

    if _scatter_fail(f"mpstat-{host}"):
        return _sysstat_missing("mpstat")

    # Determine CPU count from context or default to 4
    cpu_count = 4
    if isinstance(ctx, dict):
        cpu_count = ctx.get("cpu_count", 4)

    header = (
        f"Linux 5.14.0-362.24.1.el9_3.x86_64 ({host})   "
        f"07/04/2026   _x86_64_   ({cpu_count} CPU)\n\n"
    )
    col_header = (
        "12:00:00 AM  CPU    %usr   %nice    %sys %iowait    %irq   %soft  %steal  %guest  %gnice   %idle\n"
    )
    rows = []
    for i in range(count):
        rows.append(
            f"12:00:0{i} AM  all    2.20    0.00    0.48    0.01    0.00    0.01    0.00    0.00    0.00   97.30\n"
        )
        for cpu_id in range(cpu_count):
            usr = 2.0 + cpu_id * 0.1
            rows.append(
                f"12:00:0{i} AM  {cpu_id:>3}    {usr:.2f}    0.00    0.50    0.00    0.00    0.01    0.00    0.00    0.00   {97.49 - usr:.2f}\n"
            )
        rows.append("\n")

    stdout = header + col_header + "".join(rows)

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Per-CPU statistics collected ({count} sample(s) at {interval}s interval)."
        ),
    )


def _sim_uptime(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    # Extract uptime from context if available
    uptime_str = "14 days, 3:22"
    if isinstance(ctx, dict):
        uptime_str = ctx.get("uptime", "14 days, 3:22")

    # Realistic load averages
    load1, load5, load15 = "0.15", "0.22", "0.18"
    if isinstance(ctx, dict):
        la = ctx.get("load_avg", [0.15, 0.22, 0.18])
        load1, load5, load15 = str(la[0]), str(la[1]), str(la[2])

    stdout = (
        f" 12:00:00 up {uptime_str},  2 users,  "
        f"load average: {load1}, {load5}, {load15}\n"
    )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="System uptime and load averages retrieved.",
    )


def _sim_load(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # /proc/loadavg format: "load1 load5 load15 runnable/total last_pid"
    load1, load5, load15 = "0.15", "0.22", "0.18"
    if isinstance(ctx, dict):
        la = ctx.get("load_avg", [0.15, 0.22, 0.18])
        load1, load5, load15 = str(la[0]), str(la[1]), str(la[2])

    stdout = f"{load1} {load5} {load15} 1/312 58423\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="System load averages (1m, 5m, 15m) retrieved from /proc/loadavg.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "sar":    _sim_sar,
    "iostat": _sim_iostat,
    "vmstat": _sim_vmstat,
    "mpstat": _sim_mpstat,
    "uptime": _sim_uptime,
    "load":   _sim_load,
}


def simulate_performance(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'performance' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           performance ToolSpec (sar, iostat, vmstat, mpstat, uptime, load).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.

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
            f"simulate_performance: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
