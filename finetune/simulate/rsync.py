"""finetune/simulate/rsync.py — Rocky Linux 9 output simulator for the 'rsync' tool.

Public API
----------
simulate_rsync(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/rsync.py
    args : dict of op arguments (src and dest required for all ops)
    ctx  : system context string from make_context(), OR a profile dict.
           Supported via isinstance checks (mirrors services.py pattern).

Realism model
-------------
* Exit codes mirror real rsync behaviour:
    0  — success
    1  — general syntax/usage error
    11 — error in file I/O (e.g. source not found, permission denied)
    23 — partial transfer (some files skipped)
    127 — rsync binary not found
* stdout reflects real Rocky 9 rsync itemize-changes and stats formats.
* Failure triggers are deterministic via token checks and hash scatter.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic language).

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular import).
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


def _path_not_found(path: str) -> bool:
    """Deterministically decide if a path should trigger a not-found error.

    Triggers: token 'notfound', 'missing', 'bogus', 'noexist', 'broken',
    'fail' in the lowercase path; OR a hash-based 15% scatter.
    """
    lower = path.lower()
    for tok in ("notfound", "missing", "bogus", "noexist", "broken", "fail"):
        if tok in lower:
            return True
    h = int(hashlib.md5(path.encode()).hexdigest(), 16)
    return h % 20 == 0


def _hash_scatter(key: str, modulus: int) -> int:
    """Return a deterministic int in [0, modulus) for scatter decisions."""
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % modulus


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_dry_run(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    src = args.get("src", "/src/")
    dest = args.get("dest", "/dest/")

    if _path_not_found(src):
        stderr = f"rsync: [sender] change_dir \"{src}\" failed: No such file or directory (2)\n"
        return _make_result(
            exit_code=11,
            stdout="",
            stderr=stderr,
            summary=f"Dry run failed: source path '{src}' was not found or is not accessible.",
        )

    # Build realistic itemize-changes output
    src_base = src.rstrip("/").split("/")[-1] or "data"
    files = [
        f">f+++++++++ {src_base}/config.conf",
        f">f+++++++++ {src_base}/data.db",
        f">f.st...... {src_base}/logs/app.log",
        f">f+++++++++ {src_base}/scripts/deploy.sh",
        f">f.st...... {src_base}/var/run/pid",
    ]
    # Hash-based scatter for number of files shown
    n = 2 + _hash_scatter(src + dest, 4)
    shown = files[:n]
    stdout = "\n".join(shown) + "\n"
    stdout += f"\nsent 1,234 bytes  received 92 bytes  2,652.00 bytes/sec\n"
    stdout += f"total size is 284,502  speedup is 214.07 (DRY RUN)\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Dry run complete: {len(shown)} file(s) would be transferred from '{src}' to '{dest}'.",
    )


def _sim_sync(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    src = args.get("src", "/src/")
    dest = args.get("dest", "/dest/")

    if _path_not_found(src):
        stderr = f"rsync: [sender] change_dir \"{src}\" failed: No such file or directory (2)\n"
        return _make_result(
            exit_code=11,
            stdout="",
            stderr=stderr,
            summary=f"Sync failed: source path '{src}' was not found or is not accessible.",
        )

    # Permission denied scatter (~10%)
    if _hash_scatter(src + dest + "sync", 10) == 0:
        stderr = f"rsync: [Receiver] mkstemp \"{dest}/.tmpXXXXXX\" failed: Permission denied (13)\n"
        return _make_result(
            exit_code=23,
            stdout="",
            stderr=stderr,
            summary=f"Sync from '{src}' to '{dest}' failed (exit 23): permission denied writing to destination.",
        )

    n = 3 + _hash_scatter(src, 5)
    stdout = (
        f"sending incremental file list\n"
        f"./\n"
    )
    for i in range(1, n + 1):
        stdout += f"file{i:03d}.dat\n"
    stdout += (
        f"\nsent {n * 4096:,} bytes  received 134 bytes  {(n * 4096 + 134) * 2 / 60:,.2f} bytes/sec\n"
        f"total size is {n * 4096 * 12:,}  speedup is 12.00\n"
    )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Sync from '{src}' to '{dest}' completed successfully.",
    )


def _sim_sync_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    src = args.get("src", "/src/")
    dest = args.get("dest", "/dest/")

    if _path_not_found(src):
        stderr = f"rsync: [sender] change_dir \"{src}\" failed: No such file or directory (2)\n"
        return _make_result(
            exit_code=11,
            stdout="",
            stderr=stderr,
            summary=f"Sync with delete failed: source path '{src}' was not found or is not accessible.",
        )

    n = 2 + _hash_scatter(src + dest + "delete", 4)
    deleted = 1 + _hash_scatter(dest, 3)

    stdout = (
        f"sending incremental file list\n"
        f"deleting obsolete_backup.tar.gz\n"
    )
    for i in range(1, deleted):
        stdout += f"deleting old_file_{i:02d}.bak\n"
    for i in range(1, n + 1):
        stdout += f"current_file_{i:03d}.dat\n"
    stdout += (
        f"\nsent {n * 8192:,} bytes  received 178 bytes  {(n * 8192 + 178) / 30:,.2f} bytes/sec\n"
        f"total size is {n * 8192 * 10:,}  speedup is 10.00\n"
    )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Sync with delete from '{src}' to '{dest}' completed; "
            "files absent from source were removed from destination."
        ),
    )


def _sim_progress(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    src = args.get("src", "/src/")
    dest = args.get("dest", "/dest/")

    if _path_not_found(src):
        stderr = f"rsync: [sender] change_dir \"{src}\" failed: No such file or directory (2)\n"
        return _make_result(
            exit_code=11,
            stdout="",
            stderr=stderr,
            summary=f"Transfer estimate failed: source path '{src}' was not found or is not accessible.",
        )

    n = 4 + _hash_scatter(src + dest + "progress", 6)
    total_bytes = n * 1024 * 1024 + _hash_scatter(src, 512) * 1024

    stdout = (
        f"sending incremental file list\n"
        f"\n"
    )
    for i in range(1, n + 1):
        fsize = (i * 256 + _hash_scatter(src + str(i), 512)) * 1024
        stdout += f"file_{i:03d}.dat\n"
        stdout += f"      {fsize:,}  100%    0.00kB/s    0:00:00 (xfr#{i}, to-chk={n-i}/{n})\n"

    stdout += (
        f"\nNumber of files: {n} (reg: {n})\n"
        f"Number of created files: {n}\n"
        f"Number of deleted files: 0\n"
        f"Number of regular files transferred: {n}\n"
        f"Total file size: {total_bytes:,} bytes\n"
        f"Total transferred file size: {total_bytes:,} bytes\n"
        f"Literal data: 0 bytes\n"
        f"Matched data: 0 bytes\n"
        f"File list size: {n * 32}\n"
        f"File list generation time: 0.001 seconds\n"
        f"File list transfer time: 0.000 seconds\n"
        f"Total bytes sent: {n * 48 + 1200:,}\n"
        f"Total bytes received: 134\n"
        f"\nsent {n * 48 + 1200:,} bytes  received 134 bytes  {(n * 48 + 1334) * 2:,} bytes/sec\n"
        f"total size is {total_bytes:,}  speedup is {total_bytes // max(1, n * 48 + 1200):.2f} (DRY RUN)\n"
    )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Transfer estimate for '{src}' to '{dest}' completed; "
            "see output for file counts and size totals."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "dry-run": _sim_dry_run,
    "sync": _sim_sync,
    "sync-delete": _sim_sync_delete,
    "progress": _sim_progress,
}


def simulate_rsync(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'rsync' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in
           core/tools/rsync.py (dry-run, sync, sync-delete, progress).
    args : argument dict (src, dest expected; defaults applied per-op).
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
            f"simulate_rsync: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
