"""finetune/simulate/at.py — Rocky Linux 9 output simulator for the 'at' tool.

Public API
----------
simulate_at(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 3 real operations declared in core/tools/at.py
           ('atq', 'schedule', 'atrm')
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict. Both forms are supported via isinstance checks.

Realism model
-------------
* atq output mirrors real Rocky 9 at(1) format:
    <job_id>\t<date/time>\t<queue>\t<user>
* at schedule writes "job N at <time>" to stderr (at(1) convention on Linux).
* atrm exits 0 on success, 1 on missing/invalid job.
* Deterministic failure scatter (hash-based) provides variety.

I2 compliance
-------------
All summary strings are I2-clean. No AI/LLM/model/agent/agentic/neural language.

INV-read-only-core: this module imports NOTHING from core/ directly and nothing
from finetune.coreimports (avoids circular deps in Phase-13 __init__ import).
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


def _current_user(ctx: Any) -> str:
    """Extract current user from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("current_user", "root")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("user:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return "root"


def _job_exists(job_id: str) -> bool:
    """Deterministically decide if a job ID looks valid/present.

    Triggers not-found: the literal strings 'notfound', 'missing', 'bogus',
    '0', or a negative number. Hash-based 15% scatter adds variety.
    """
    lower = job_id.strip().lower()
    for tok in ("notfound", "missing", "bogus", "invalid"):
        if tok in lower:
            return False
    # Bare zero or negative-looking string
    try:
        n = int(job_id)
        if n <= 0:
            return False
    except ValueError:
        # Non-numeric job id — treat as invalid
        return False
    # Hash-based scatter (~15% not found)
    h = int(hashlib.md5(job_id.encode()).hexdigest(), 16)
    return h % 7 != 0


def _pending_jobs(ctx: Any, user: str) -> list[tuple[str, str]]:
    """Return a list of (job_id, time_str) pairs from the context, if any."""
    if isinstance(ctx, dict):
        return ctx.get("at_jobs", [])
    return []


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_atq(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate atq — list pending at jobs."""
    queue_filter: str = args.get("queue", "")
    user = _current_user(ctx)

    # Pull any jobs declared in the context profile
    jobs = _pending_jobs(ctx, user)

    if not jobs:
        # Use a hash of the ctx string for deterministic variety
        ctx_key = str(ctx)[:64] if ctx else ""
        h = int(hashlib.md5(ctx_key.encode()).hexdigest(), 16)
        if h % 5 == 0:
            # Empty queue branch
            return _make_result(
                exit_code=0,
                stdout="",
                stderr="",
                summary="No pending at jobs in the queue.",
            )
        # Generate a small set of realistic jobs
        count = 1 + (h % 4)
        lines = []
        for i in range(count):
            jid = 10 + i
            q = queue_filter if queue_filter else "a"
            lines.append(
                f"{jid}\tSat Jul  4 23:{30 + i * 10:02d}:00 2026 {q}\t{user}"
            )
        stdout = "\n".join(lines) + "\n"
        job_count = len(lines)
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Found {job_count} pending at job(s) in the queue.",
        )

    # Build output from context-supplied jobs
    lines = []
    for jid, time_str in jobs:
        q = queue_filter if queue_filter else "a"
        lines.append(f"{jid}\t{time_str} {q}\t{user}")
    if queue_filter:
        lines = [l for l in lines if queue_filter in l]
    stdout = "\n".join(lines) + "\n" if lines else ""
    job_count = len(lines)
    if job_count == 0:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"No pending at jobs found in queue '{queue_filter}'.",
        )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {job_count} pending at job(s) in the queue.",
    )


def _sim_schedule(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate at <time> — schedule a command."""
    time_spec: str = args.get("time", "now + 1 hour")
    command: str = args.get("command", "echo hello")

    # at(1) on Linux writes "job N at <time>" to stderr on success
    # Determine a synthetic job id from the hash of time+command
    h = int(hashlib.md5((time_spec + command).encode()).hexdigest(), 16)

    # Failure branch: invalid/unrecognized time spec
    invalid_tokens = ("yesterday", "invalid", "notadate", "badtime")
    time_lower = time_spec.lower()
    if any(tok in time_lower for tok in invalid_tokens):
        stderr = f"Garbled time\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to schedule job at '{time_spec}' (exit 1).",
        )

    # Success
    job_id = 1 + (h % 9999)
    stderr = (
        f"warning: commands will be executed using /bin/sh\n"
        f"job {job_id} at {time_spec}\n"
    )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr,
        summary=f"Job scheduled to run at '{time_spec}'.",
    )


def _sim_atrm(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate atrm <job_id> — remove a queued at job."""
    job_id: str = args.get("job_id", "0")

    if not _job_exists(job_id):
        stderr = f"Cannot find jobid {job_id}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove at job {job_id} (exit 1).",
        )

    # Success: atrm produces no stdout on Rocky 9
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"At job {job_id} removed from the queue.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "atq": _sim_atq,
    "schedule": _sim_schedule,
    "atrm": _sim_atrm,
}


def simulate_at(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'at' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 3 real ops declared in the
           at ToolSpec (atq, schedule, atrm).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with optional 'at_jobs', 'current_user' keys.

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
            f"simulate_at: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
