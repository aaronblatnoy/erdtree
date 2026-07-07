"""finetune/simulate/perf.py — Rocky Linux 9 output simulator for the 'perf' tool.

Public API
----------
simulate_perf(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 3 real operations declared in core/tools/perf.py
           (stat, top, record)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(), OR a profile
           dict — both forms are supported via isinstance.

Realism model
-------------
* perf stat outputs hardware counter tables to stderr (kernel default).
* perf top --stdio outputs a ranked symbol table.
* perf record outputs a progress line to stderr and writes perf.data.
* Failure triggers: perf not installed (exit 127), insufficient privileges
  for kernel-level counters (exit 1 with "perf_event_open failed" or
  "Permission denied"), or a hash-based ~15% scatter for variety.

I2 compliance
-------------
All summary strings are I2-clean. No forbidden terms (AI, LLM, model,
agent, agentic, neural, language model) appear in any summary.

INV-read-only-core: this module imports NOTHING from core/ directly and
NOTHING from finetune.coreimports (avoids circular deps when Phase-13
__init__ imports simulator modules before coreimports is settled).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic output lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _perf_missing(ctx: Any) -> bool:
    """Return True if perf appears to be absent from the context."""
    if isinstance(ctx, dict):
        pkgs = ctx.get("installed_packages", [])
        # If a package list is present and perf is not in it, treat as missing
        if pkgs and not any("perf" in str(p).lower() for p in pkgs):
            return True
    return False


def _should_fail(seed: str) -> bool:
    """Deterministic ~15% failure scatter."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
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

def _sim_stat(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    command = args.get("command", "sleep 1")
    events = args.get("events", "") or ""
    repeats = max(1, min(int(args.get("repeats", 1) or 1), 10))

    if _perf_missing(ctx):
        return _make_result(
            exit_code=127,
            stdout="",
            stderr="perf: command not found\n",
            summary=f"perf stat failed for command '{command}': perf binary not found (exit 127).",
        )

    if _should_fail(command + "stat"):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=(
                "perf_event_open failed, returning with 4 (Interrupted system call)\n"
                "Hint: /proc/sys/kernel/perf_event_paranoid is set to 4.\n"
                "Consider lowering it (e.g. 'sysctl -w kernel.perf_event_paranoid=1').\n"
            ),
            summary=f"perf stat failed for command '{command}': perf_event_open denied (exit 1).",
        )

    # Realistic perf stat output (printed to stderr by perf)
    event_line = f" -e {events}" if events else ""
    repeat_note = f" ({repeats} runs, averaged)" if repeats > 1 else ""
    stderr = (
        f"\n"
        f" Performance counter stats for '{command}'{event_line}{repeat_note}:\n"
        f"\n"
        f"          1,234,567      cycles                    #    2.456 GHz\n"
        f"            987,654      instructions              #    0.80  insn per cycle\n"
        f"             12,345      cache-references          #    9.987 M/sec\n"
        f"              1,234      cache-misses              #   10.000 % of all cache refs\n"
        f"             98,765      branches                  #   79.987 M/sec\n"
        f"              2,345      branch-misses             #    2.375 % of all branches\n"
        f"\n"
        f"       0.005032291 seconds time elapsed\n"
        f"\n"
        f"       0.004200000 seconds user\n"
        f"       0.000900000 seconds sys\n"
        f"\n"
    )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr,
        summary=f"perf stat completed for command '{command}'.",
    )


def _sim_top(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    duration = max(1, min(int(args.get("duration", 10) or 10), 300))
    events = args.get("events", "") or ""
    sort = args.get("sort", "") or ""

    if _perf_missing(ctx):
        return _make_result(
            exit_code=127,
            stdout="",
            stderr="perf: command not found\n",
            summary=f"perf top failed after {duration}s: perf binary not found (exit 127).",
        )

    if _should_fail("top" + str(duration)):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=(
                "Error: The sys_perf_event_open() syscall returned with 1 (Operation not permitted).\n"
                "/proc/sys/kernel/perf_event_paranoid value is 4.\n"
            ),
            summary=f"perf top failed after {duration}s: insufficient privileges for kernel counters (exit 1).",
        )

    # Realistic perf top --stdio output
    header = (
        f"# Samples: 1K of event '{events or 'cycles'}'\n"
        f"# Event count (approx.): 1234567890\n"
        f"#\n"
        f"# Overhead  Command       Shared Object         Symbol\n"
        f"# ........  ............  ....................  ......................................\n"
        f"#\n"
    )
    rows = (
        f"    15.23%  httpd         httpd                 [.] ap_run_handler\n"
        f"    12.40%  [kernel]      [kernel.vmlinux]      [k] schedule\n"
        f"     9.87%  nginx         nginx                 [.] ngx_http_process_request\n"
        f"     7.55%  python3       python3.9             [.] PyEval_EvalFrameDefault\n"
        f"     5.32%  mysqld        mysqld                [.] ha_innobase::index_read\n"
        f"     4.10%  java          libjvm.so             [.] CompileBroker::compile_method\n"
        f"     3.98%  [kernel]      [kernel.vmlinux]      [k] copy_user_enhanced_fast_string\n"
        f"     2.77%  sshd          libcrypto.so.1.1      [.] AES_encrypt\n"
        f"     1.55%  [kernel]      [kernel.vmlinux]      [k] __softirqentry_text_start\n"
        f"     1.02%  bash          bash                  [.] execute_command\n"
    )
    stdout = header + rows
    sort_note = f" (sorted by {sort})" if sort else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"perf top ran for {duration}s and returned CPU profiling data{sort_note}.",
    )


def _sim_record(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    output = args.get("output", "") or "perf.data"
    events = args.get("events", "") or ""
    pid_raw = args.get("pid")
    pid = int(pid_raw) if pid_raw is not None else 0
    command = args.get("command", "") or ""
    duration_raw = args.get("duration")
    duration = max(1, min(int(duration_raw) if duration_raw is not None else 10, 300))

    if _perf_missing(ctx):
        return _make_result(
            exit_code=127,
            stdout="",
            stderr="perf: command not found\n",
            summary=f"perf record failed: perf binary not found (exit 127).",
        )

    if _should_fail(output + str(pid)):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=(
                "Error: sys_perf_event_open() syscall returned with 13 (Permission denied).\n"
                "Hint: Check /proc/sys/kernel/perf_event_paranoid and kptr_restrict.\n"
            ),
            summary=f"perf record failed (exit 1); data may not have been written to '{output}'.",
        )

    target = f"PID {pid}" if pid and pid > 0 else (command if command else f"{duration}s sleep")
    event_note = f" ({events})" if events else ""
    stderr = (
        f"[ perf record: Woken up 1 times to write data ]\n"
        f"[ perf record: Captured and wrote 0.024 MB {output} ({42} samples) ]\n"
    )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr,
        summary=f"perf record completed; data written to '{output}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "stat": _sim_stat,
    "top": _sim_top,
    "record": _sim_record,
}


def simulate_perf(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'perf' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of: stat, top, record.
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — either a snapshot_text str or a profile dict.

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
            f"simulate_perf: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
