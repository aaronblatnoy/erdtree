"""finetune/simulate/aide.py — Rocky Linux 9 output simulator for the 'aide' tool.

Public API
----------
simulate_aide(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/aide.py
           (check, init, update, db_status)
    args : dict of op arguments (may be {} — all args are optional)
    ctx  : system context string produced by make_context(), OR a profile
           dict (same shape as _PROFILES entries).  Both forms supported
           via isinstance.

Realism model
-------------
* Exit codes mirror real AIDE behaviour on Rocky Linux 9:
    0  — success / no changes (check)
    1  — AIDE found differences (check)
    2  — AIDE DB or config not found
    14 — aide --check exit code when changes detected
* stdout/stderr reflect actual AIDE 0.16.x (Rocky 9 default) output:
  structured change reports with section headers and attribute lines.
* Deterministic failure branches keyed on 'notfound'/'missing'/'broken'
  tokens in the config path, or a hash-based scatter for variety.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic/neural
language). The test suite asserts this.

INV-read-only-core: imports NOTHING from core/ and NOTHING from
finetune.coreimports (avoids circular import when Phase-13 __init__
imports simulators before coreimports is fully resolved).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _db_missing(conf: str) -> bool:
    """Deterministically decide if the AIDE DB should be reported missing.

    Triggers: 'notfound', 'missing', 'broken', 'noexist' in the conf path;
    OR a hash-based ~10% scatter.
    """
    lower = conf.lower()
    for tok in ("notfound", "missing", "broken", "noexist", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5(conf.encode()).hexdigest(), 16)
    return h % 20 == 0


def _aide_has_changes(conf: str) -> bool:
    """Deterministically decide if aide --check should report differences."""
    h = int(hashlib.md5((conf + "changes").encode()).hexdigest(), 16)
    # ~35% chance of finding changes — realistic for an active system
    return h % 3 == 0


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

def _sim_check(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    conf = args.get("config", "/etc/aide.conf")

    if _db_missing(conf):
        stderr = (
            f"aide: cannot open database file '/var/lib/aide/aide.db.gz': "
            f"No such file or directory\n"
            f"Hint: run 'aide --init' to create the reference database.\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=(
                "aide integrity check failed — reference database not found. "
                "Run 'aide --init' to create it."
            ),
        )

    if _aide_has_changes(conf):
        stdout = (
            "AIDE 0.16.2 found differences between database and filesystem!!\n"
            "\n"
            "Start timestamp: 2026-07-06 03:14:22 +0000 (AIDE 0.16.2)\n"
            "\n"
            "Summary:\n"
            "  Total number of entries:\t73141\n"
            "  Added entries:\t\t0\n"
            "  Removed entries:\t\t0\n"
            "  Changed entries:\t\t4\n"
            "\n"
            "---------------------------------------------------\n"
            "Changed entries:\n"
            "---------------------------------------------------\n"
            "\n"
            "f   = ..    : /etc/passwd\n"
            "f   = ..    : /etc/shadow\n"
            "f   = ..    : /etc/group\n"
            "f   = ..    : /var/log/audit/audit.log\n"
            "\n"
            "---------------------------------------------------\n"
            "Detailed information about changes:\n"
            "---------------------------------------------------\n"
            "\n"
            "File: /etc/passwd\n"
            " Mtime    : 2026-07-05 22:10:01               | 2026-07-06 01:55:14\n"
            " Ctime    : 2026-07-05 22:10:01               | 2026-07-06 01:55:14\n"
            " SHA256   : 3Rw7kFHu...                       | 9pQmZj2v...\n"
            "\n"
            "End timestamp: 2026-07-06 03:16:08 +0000\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=(
                "aide integrity check detected 4 changed entries; "
                "review stdout for the list of affected files."
            ),
        )

    # Clean run — no changes
    stdout = (
        "AIDE 0.16.2, compiled with the following options:\n"
        "\n"
        "Start timestamp: 2026-07-06 03:14:22 +0000 (AIDE 0.16.2)\n"
        "\n"
        "Summary:\n"
        "  Total number of entries:\t73141\n"
        "  Added entries:\t\t0\n"
        "  Removed entries:\t\t0\n"
        "  Changed entries:\t\t0\n"
        "\n"
        "---------------------------------------------------\n"
        "No differences found.\n"
        "---------------------------------------------------\n"
        "\n"
        "End timestamp: 2026-07-06 03:15:49 +0000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="aide integrity check passed — no unexpected changes detected.",
    )


def _sim_init(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    conf = args.get("config", "/etc/aide.conf")

    if _db_missing(conf):
        stderr = (
            f"aide: cannot open configuration file '{conf}': "
            f"No such file or directory\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=(
                f"aide database initialisation failed — "
                f"configuration file '{conf}' not found."
            ),
        )

    stdout = (
        "AIDE 0.16.2 initialized database at /var/lib/aide/aide.db.new.gz\n"
        "\n"
        "Start timestamp: 2026-07-06 03:17:00 +0000 (AIDE 0.16.2)\n"
        "\n"
        "Number of entries:\t73141\n"
        "\n"
        "---------------------------------------------------\n"
        "The attributes of the (uncompressed) database(s):\n"
        "---------------------------------------------------\n"
        "\n"
        "/var/lib/aide/aide.db.new.gz\n"
        "  MD5      : YmUwZmFjOT...==\n"
        "  SHA1     : MDAwMDAwMD...==\n"
        "  RMD160   : MzM4NzM3Mj...==\n"
        "  TIGER    : MDA2NDY4ND...==\n"
        "  SHA256   : NDYzNzE3OT...==\n"
        "  SHA512   : NzkyNzgxNj...==\n"
        "\n"
        "End timestamp: 2026-07-06 03:18:32 +0000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            "aide database initialised successfully. "
            "Move aide.db.new.gz to aide.db.gz to activate the new baseline."
        ),
    )


def _sim_update(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    conf = args.get("config", "/etc/aide.conf")

    if _db_missing(conf):
        stderr = (
            f"aide: cannot open database file '/var/lib/aide/aide.db.gz': "
            f"No such file or directory\n"
            f"Hint: run 'aide --init' to create the reference database first.\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=(
                "aide database update failed — reference database not found. "
                "Run 'aide --init' to create it first."
            ),
        )

    stdout = (
        "AIDE 0.16.2 found differences between database and filesystem.\n"
        "\n"
        "Start timestamp: 2026-07-06 03:19:00 +0000 (AIDE 0.16.2)\n"
        "\n"
        "Summary:\n"
        "  Total number of entries:\t73141\n"
        "  Added entries:\t\t0\n"
        "  Removed entries:\t\t0\n"
        "  Changed entries:\t\t2\n"
        "\n"
        "Number of entries in the new database:\t73141\n"
        "\n"
        "---------------------------------------------------\n"
        "The attributes of the (uncompressed) database(s):\n"
        "---------------------------------------------------\n"
        "\n"
        "/var/lib/aide/aide.db.new.gz\n"
        "  SHA256   : OGE2MzA1YW...==\n"
        "\n"
        "End timestamp: 2026-07-06 03:21:05 +0000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            "aide database updated successfully. "
            "The new baseline reflects the current filesystem state."
        ),
    )


def _sim_db_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    db_path = args.get("db_path", "/var/lib/aide/aide.db.gz")

    if _db_missing(db_path):
        stderr = (
            f"stat: cannot statx '{db_path}': No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"aide database file not found or inaccessible at '{db_path}'. "
                "Run 'aide --init' to create it."
            ),
        )

    # Produce realistic stat(1) output for the AIDE DB file
    stdout = (
        f"  File: {db_path}\n"
        f"  Size: 2457600\t\tBlocks: 4800\t IO Block: 4096\tregular file\n"
        f"Device: fd01h/64769d\tInode: 131073\t Links: 1\n"
        f"Access: (0600/-rw-------)\t Uid: (    0/    root)\t Gid: (    0/    root)\n"
        f"Context: system_u:object_r:aide_db_t:s0\n"
        f"Access: 2026-07-06 03:15:49.134211042 +0000\n"
        f"Modify: 2026-07-05 22:00:11.882001000 +0000\n"
        f"Change: 2026-07-05 22:00:11.882001000 +0000\n"
        f" Birth: -\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"aide database file found at '{db_path}'; details in stdout.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "check":     _sim_check,
    "init":      _sim_init,
    "update":    _sim_update,
    "db_status": _sim_db_status,
}


def simulate_aide(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'aide' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in
           core/tools/aide.py (check, init, update, db_status).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with hostname/active_services etc.

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
            f"simulate_aide: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
