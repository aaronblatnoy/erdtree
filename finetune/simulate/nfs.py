"""finetune/simulate/nfs.py — Rocky Linux 9 output simulator for the 'nfs' tool.

Public API
----------
simulate_nfs(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 8 real operations declared in core/tools/nfs.py
    args : dict of op arguments (may be {} for ops with no required args)
    ctx  : system context string produced by make_context(), OR a profile
           dict — both forms supported via isinstance checks.

Realism model
-------------
* showmount -e: produces a typical 'Export list for <server>:' table.
* exportfs -v: produces per-export lines with options.
* exportfs -r: minimal output, exits 0 on success.
* exportfs -u: minimal output, or an error if the target is not found.
* cat /etc/exports: typical /etc/exports content.
* systemctl start/stop nfs-server: minimal output matching systemctl behaviour.
* mount -t nfs: minimal output; fails with a realistic error for bad targets.
* Failure triggers: server/target names containing 'notfound', 'noexist',
  'broken', 'fail', 'unreachable', or 'missing' trigger error branches.
  A hash-based 15% scatter adds variety among plausible-looking names.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/agent/model language).

INV-read-only-core: imports NOTHING from core/ and NOTHING from finetune.coreimports.
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
    """Extract hostname from ctx for realistic log lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "nfs-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "nfs-host"


def _should_fail(name: str) -> bool:
    """Deterministically decide if a name should trigger a failure branch.

    Triggers: failure tokens in the name, or a hash-based ~15% scatter.
    """
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "unreachable", "missing", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _nfs_exports_active(ctx: Any) -> list[str]:
    """Return a list of active export paths from the context."""
    if isinstance(ctx, dict):
        return ctx.get("nfs_exports", ["/srv/nfs/data", "/srv/nfs/backups"])
    return ["/srv/nfs/data", "/srv/nfs/backups"]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_showmount(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    server = args.get("server", "nfs-server.example.com")

    if _should_fail(server):
        stderr = (
            f"clnt_create: RPC: Port mapper failure - Unable to receive: "
            f"errno 111 (Connection refused)\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Could not reach NFS server '{server}' to retrieve its export list.",
        )

    exports = _nfs_exports_active(ctx)
    lines = [f"Export list for {server}:"]
    for exp in exports:
        lines.append(f"{exp}  *")
    stdout = "\n".join(lines) + "\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved NFS export list from '{server}'.",
    )


def _sim_exportfs_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    exports = _nfs_exports_active(ctx)

    if not exports:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="No active NFS exports found on this host.",
        )

    lines = []
    for exp in exports:
        lines.append(
            f"{exp}  \t*(rw,wdelay,root_squash,no_subtree_check,"
            f"sec=sys,rw,root_squash,no_all_squash)"
        )
    stdout = "\n".join(lines) + "\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Active NFS exports listed successfully.",
    )


def _sim_exportfs_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # exportfs -r just re-reads /etc/exports; minimal output on success
    # Scatter a failure case based on a constant seed for the no-arg op
    h = int(hashlib.md5(b"exportfs_add_nfs").hexdigest(), 16)
    if h % 25 == 0:
        stderr = "exportfs: Failed to stat /etc/exports: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to reload NFS exports — /etc/exports not found.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="NFS exports reloaded from /etc/exports and published.",
    )


def _sim_exportfs_unexport(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    target = args.get("target", "*:/srv/nfs")

    if _should_fail(target):
        stderr = f"exportfs: Could not find '{target}' to unexport\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to revoke NFS export '{target}' — export not found.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"NFS export '{target}' revoked; clients can no longer access this share.",
    )


def _sim_exports_view(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    exports = _nfs_exports_active(ctx)

    lines = [
        "# /etc/exports — NFS server configuration",
        "# See exports(5) for full syntax.",
        "#",
    ]
    for exp in exports:
        lines.append(f"{exp}  *(rw,sync,root_squash,no_subtree_check)")

    stdout = "\n".join(lines) + "\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="NFS exports configuration displayed from /etc/exports.",
    )


def _sim_nfs_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    # Check context for whether the service is already running
    if isinstance(ctx, dict):
        active = ctx.get("active_services", [])
        if any("nfs" in s for s in active):
            return _make_result(
                exit_code=0,
                stdout="",
                stderr="",
                summary="NFS server service was already running; start completed without error.",
            )

    # Hash-based failure scatter
    h = int(hashlib.md5((host + "nfs_start").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            "Job for nfs-server.service failed because the control process exited "
            "with error code.\n"
            "See 'systemctl status nfs-server.service' and "
            "'journalctl -xeu nfs-server.service' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to start the NFS server service; check the service configuration.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="NFS server service started.",
    )


def _sim_nfs_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    # Already stopped — systemctl stop is idempotent (exits 0)
    if isinstance(ctx, dict):
        active = ctx.get("active_services", [])
        if not any("nfs" in s for s in active):
            return _make_result(
                exit_code=0,
                stdout="",
                stderr="",
                summary="NFS server service was already inactive; stop completed without error.",
            )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="NFS server service stopped.",
    )


def _sim_mount_client(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    server = args.get("server", "nfs-server.example.com")
    path = args.get("path", "/srv/nfs")
    mountpoint = args.get("mountpoint", "/mnt/nfs")
    source = f"{server}:{path}"

    if _should_fail(server) or _should_fail(mountpoint):
        stderr = (
            f"mount.nfs: Connection timed out\n"
            f"mount.nfs: mounting {source} failed, reason given by server: No such file or directory\n"
        )
        return _make_result(
            exit_code=32,
            stdout="",
            stderr=stderr,
            summary=f"Failed to mount NFS share '{source}' at '{mountpoint}' — connection timed out or path not found.",
        )

    # Permission denied path (SELinux / kernel AVC)
    h = int(hashlib.md5((source + mountpoint).encode()).hexdigest(), 16)
    if h % 18 == 0:
        stderr = (
            f"mount.nfs: access denied by server while mounting {source}\n"
            f"type=AVC msg=audit(1751500000.123:456): avc:  denied  {{ read }} for  "
            f"pid=1234 comm=\"mount\" name=\"{path}\" dev=\"nfs\" ino=2\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to mount NFS share '{source}' at '{mountpoint}' — access denied.  "
                "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
                "or 'journalctl -t setroubleshoot' for denial details."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"NFS share '{source}' mounted at '{mountpoint}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "showmount":          _sim_showmount,
    "exportfs_list":      _sim_exportfs_list,
    "exportfs_add":       _sim_exportfs_add,
    "exportfs_unexport":  _sim_exportfs_unexport,
    "exports_view":       _sim_exports_view,
    "nfs_start":          _sim_nfs_start,
    "nfs_stop":           _sim_nfs_stop,
    "mount_client":       _sim_mount_client,
}


def simulate_nfs(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'nfs' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 8 real ops in core/tools/nfs.py.
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict with
           'nfs_exports', 'active_services', 'hostname' keys.

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
            f"simulate_nfs: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
