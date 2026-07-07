"""finetune/simulate/tar.py — Rocky Linux 9 output simulator for the 'tar' tool.

Public API
----------
simulate_tar(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/tar.py
           (list, create, extract, verify, create_gz, create_bz2, create_xz)
    args : dict of op arguments (may be sparse; defaults applied per-op)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real tar behaviour on Rocky Linux 9 (GNU tar 1.34+):
    0  — success
    1  — warnings (differences found in verify / file changed during archive)
    2  — fatal error (archive not found, permission denied, bad format)
* stdout reflects actual tar listing format (verbose: permissions, owner, size,
  date, name) and stderr contains GNU tar error messages.
* Failure triggers are deterministic: archive names containing "notfound",
  "missing", "bogus", or "noexist" trigger a not-found failure.  A ~15%
  hash-based scatter adds variety.

I2 compliance
-------------
All summary strings are I2-clean.  No forbidden terms appear anywhere.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (avoids circular deps during Phase-13
__init__ aggregation).
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


def _archive_not_found(archive: str) -> bool:
    """Deterministically decide if an archive path triggers a not-found error."""
    lower = archive.lower()
    for tok in ("notfound", "missing", "bogus", "noexist", "broken", "fail"):
        if tok in lower:
            return True
    h = int(hashlib.md5(archive.encode()).hexdigest(), 16)
    return h % 20 == 0


def _archive_permission_denied(archive: str) -> bool:
    """Deterministically trigger a permission-denied branch for variety."""
    lower = archive.lower()
    if "denied" in lower or "noperm" in lower or "root_only" in lower:
        return True
    h = int(hashlib.md5((archive + "perm").encode()).hexdigest(), 16)
    return h % 30 == 0


def _fake_listing(archive: str, verbose: bool = True) -> tuple[str, int]:
    """Produce a plausible tar listing for the archive path."""
    base = archive.rsplit("/", 1)[-1].replace(".tar.gz", "").replace(
        ".tar.bz2", "").replace(".tar.xz", "").replace(".tar", "")
    entries = [
        f"drwxr-xr-x root/root         0 2026-07-01 00:00 {base}/",
        f"-rw-r--r-- root/root      4096 2026-07-01 00:01 {base}/README",
        f"-rw-r--r-- root/root     16384 2026-07-01 00:01 {base}/config.conf",
        f"-rwxr-xr-x root/root      8192 2026-07-01 00:01 {base}/bin/start.sh",
        f"-rw-r--r-- root/root    102400 2026-07-01 00:01 {base}/data/records.db",
        f"-rw-r--r-- root/root      2048 2026-07-01 00:01 {base}/data/index.dat",
    ]
    stdout = "\n".join(entries) + "\n"
    return stdout, len(entries)


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar")

    if _archive_not_found(archive):
        stderr = (
            f"tar: {archive}: Cannot open: No such file or directory\n"
            f"tar: Error is not recoverable: exiting now\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Archive '{archive}' could not be opened for listing; file not found.",
        )

    if _archive_permission_denied(archive):
        stderr = (
            f"tar: {archive}: Cannot open: Permission denied\n"
            f"tar: Error is not recoverable: exiting now\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=(
                f"Archive '{archive}' could not be listed; access was denied.  "
                "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
                "or 'journalctl -t setroubleshoot' for denial details."
            ),
        )

    stdout, count = _fake_listing(archive)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Archive '{archive}' listed successfully ({count} entries).",
    )


def _sim_create(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar")
    sources = args.get("sources", ["/etc"])

    # Hash-based failure scatter (~10%)
    h = int(hashlib.md5((archive + "create").encode()).hexdigest(), 16)
    if h % 10 == 0:
        src = sources[0] if sources else "/missing"
        stderr = (
            f"tar: {src}: Cannot stat: No such file or directory\n"
            f"tar: Exiting with failure status due to previous errors\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create archive '{archive}'; one or more source paths could not be read (exit 2).",
        )

    src_count = len(sources) if isinstance(sources, list) else 1
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Archive '{archive}' created from {src_count} source path(s).",
    )


def _sim_extract(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar")
    dest = args.get("dest") or ""

    if _archive_not_found(archive):
        stderr = (
            f"tar: {archive}: Cannot open: No such file or directory\n"
            f"tar: Error is not recoverable: exiting now\n"
        )
        dest_label = dest if dest else "current directory"
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to extract archive '{archive}'; file not found (exit 2).",
        )

    if _archive_permission_denied(archive):
        stderr = (
            f"tar: {archive}: Cannot open: Permission denied\n"
            f"tar: Error is not recoverable: exiting now\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to extract archive '{archive}'; access was denied (exit 2).  "
                "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
                "or 'journalctl -t setroubleshoot' for denial details."
            ),
        )

    dest_label = dest if dest else "current directory"
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Archive '{archive}' extracted to '{dest_label}'.",
    )


def _sim_verify(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar")

    if _archive_not_found(archive):
        stderr = (
            f"tar: {archive}: Cannot open: No such file or directory\n"
            f"tar: Error is not recoverable: exiting now\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Archive '{archive}' could not be opened for verification; file not found.",
        )

    # Some archives show drift (hash-based, ~15%)
    h = int(hashlib.md5((archive + "verify").encode()).hexdigest(), 16)
    if h % 7 == 0:
        base = archive.rsplit("/", 1)[-1].replace(".tar", "")
        stdout = (
            f"tar: {base}/config.conf: Mod time differs\n"
            f"tar: {base}/data/records.db: Size differs\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=f"Archive '{archive}' verification found differences; some files have changed since archiving.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Archive '{archive}' verified; contents match the filesystem.",
    )


def _sim_create_gz(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar.gz")
    sources = args.get("sources", ["/etc"])

    h = int(hashlib.md5((archive + "gz").encode()).hexdigest(), 16)
    if h % 10 == 0:
        src = sources[0] if sources else "/missing"
        stderr = (
            f"tar: {src}: Cannot stat: No such file or directory\n"
            f"tar: Exiting with failure status due to previous errors\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create gzip archive '{archive}'; one or more source paths could not be read (exit 2).",
        )

    src_count = len(sources) if isinstance(sources, list) else 1
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Gzip-compressed archive '{archive}' created from {src_count} source path(s).",
    )


def _sim_create_bz2(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar.bz2")
    sources = args.get("sources", ["/etc"])

    h = int(hashlib.md5((archive + "bz2").encode()).hexdigest(), 16)
    if h % 10 == 0:
        src = sources[0] if sources else "/missing"
        stderr = (
            f"tar: {src}: Cannot stat: No such file or directory\n"
            f"tar: Exiting with failure status due to previous errors\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create bzip2 archive '{archive}'; one or more source paths could not be read (exit 2).",
        )

    src_count = len(sources) if isinstance(sources, list) else 1
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Bzip2-compressed archive '{archive}' created from {src_count} source path(s).",
    )


def _sim_create_xz(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    archive = args.get("archive", "/backup/archive.tar.xz")
    sources = args.get("sources", ["/etc"])

    h = int(hashlib.md5((archive + "xz").encode()).hexdigest(), 16)
    if h % 10 == 0:
        src = sources[0] if sources else "/missing"
        stderr = (
            f"tar: {src}: Cannot stat: No such file or directory\n"
            f"tar: Exiting with failure status due to previous errors\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create xz archive '{archive}'; one or more source paths could not be read (exit 2).",
        )

    src_count = len(sources) if isinstance(sources, list) else 1
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Xz-compressed archive '{archive}' created from {src_count} source path(s).",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":       _sim_list,
    "create":     _sim_create,
    "extract":    _sim_extract,
    "verify":     _sim_verify,
    "create_gz":  _sim_create_gz,
    "create_bz2": _sim_create_bz2,
    "create_xz":  _sim_create_xz,
}


def simulate_tar(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'tar' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in
           core/tools/tar.py (list, create, extract, verify, create_gz,
           create_bz2, create_xz).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

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
            f"simulate_tar: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
