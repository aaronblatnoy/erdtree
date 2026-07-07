"""finetune/simulate/stratis.py — Rocky Linux 9 output simulator for the 'stratis' tool.

Public API
----------
simulate_stratis(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/stratis.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real stratis CLI behaviour on Rocky Linux 9:
    0  — success
    1  — general error (pool/filesystem not found, device busy, etc.)
  127  — stratis binary not found (not installed)
* stdout/stderr reflect the actual stratis table output format.
* Failure triggers are deterministic: a pool/filesystem name containing
  "notfound", "missing", "broken", "fail", or "bogus" triggers failure.
  A hash-based ~15% scatter adds variety.

I2 compliance
-------------
All summary strings are I2-clean.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hostname(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _name_is_bad(name: str) -> bool:
    """Deterministically decide if a pool/filesystem name triggers a not-found error."""
    lower = name.lower()
    for tok in ("notfound", "missing", "broken", "fail", "bogus", "noexist"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
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


def _pool_exists(pool: str, ctx: Any) -> bool:
    """Check if a pool appears in the context."""
    if isinstance(ctx, dict):
        pools: list[str] = ctx.get("stratis_pools", [])
        return pool in pools
    if isinstance(ctx, str):
        return pool in ctx
    return False


def _fs_exists(pool: str, fs: str, ctx: Any) -> bool:
    """Check if a filesystem appears in the context."""
    if isinstance(ctx, dict):
        filesystems: dict = ctx.get("stratis_filesystems", {})
        return fs in filesystems.get(pool, [])
    if isinstance(ctx, str):
        return fs in ctx
    return False


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------


def _sim_pool_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """stratis pool list"""
    # Collect pools from context
    pools: list[str] = []
    if isinstance(ctx, dict):
        pools = ctx.get("stratis_pools", ["datapool", "backuppool"])
    else:
        pools = ["datapool", "backuppool"]

    if not pools:
        stdout = (
            "Name  Total Physical  Properties      UUID\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="No Stratis pools found on this host.",
        )

    lines = ["Name         Total Physical  Properties      UUID"]
    for pool in pools:
        h = int(hashlib.md5(pool.encode()).hexdigest(), 16)
        uuid = f"{h:08x}-{(h>>32)&0xffff:04x}-{(h>>48)&0xffff:04x}-{(h>>56)&0xffff:04x}-{h&0xffffffffffff:012x}"
        lines.append(f"{pool:<12} 100 GiB         C,~Ca,~Cr   {uuid}")
    stdout = "\n".join(lines) + "\n"

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {len(pools)} Stratis pool(s): {', '.join(pools)}.",
    )


def _sim_pool_create(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool", "newpool")
    blockdev = args.get("blockdev", "/dev/sdb")

    if _name_is_bad(pool):
        stderr = f"stratis: error: Pool name '{pool}' is invalid or already exists.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create Stratis pool '{pool}'; the name is invalid or already in use.",
        )

    # Check if device looks invalid
    if not blockdev.startswith("/dev/"):
        stderr = f"stratis: error: '{blockdev}' is not a valid block device.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create Stratis pool '{pool}'; '{blockdev}' is not a valid block device.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Stratis pool '{pool}' created on device '{blockdev}'.",
    )


def _sim_pool_destroy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool", "datapool")

    if _name_is_bad(pool) or not _pool_exists(pool, ctx):
        stderr = f"stratis: error: Pool '{pool}' not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to destroy Stratis pool '{pool}'; pool not found.",
        )

    # Check for filesystems still present (hash-based scatter)
    h = int(hashlib.md5((pool + "destroy").encode()).hexdigest(), 16)
    if h % 8 == 0:
        stderr = (
            f"stratis: error: Pool '{pool}' has filesystems; "
            "destroy all filesystems before destroying the pool.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to destroy Stratis pool '{pool}'; the pool still contains filesystems.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Stratis pool '{pool}' destroyed; all its filesystems and data have been removed.",
    )


def _sim_filesystem_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool") or ""

    if pool and _name_is_bad(pool):
        stderr = f"stratis: error: Pool '{pool}' not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to list filesystems; Stratis pool '{pool}' not found.",
        )

    # Build filesystem table from context
    if isinstance(ctx, dict):
        all_fs: dict = ctx.get("stratis_filesystems", {"datapool": ["rootfs", "homefs"]})
    else:
        all_fs = {"datapool": ["rootfs", "homefs"]}

    if pool:
        fs_entries = {pool: all_fs.get(pool, [])}
    else:
        fs_entries = all_fs

    lines = ["Pool Name    Name      Used      Created            Device                   UUID"]
    total = 0
    for p, fsl in fs_entries.items():
        for fs in fsl:
            h = int(hashlib.md5((p + fs).encode()).hexdigest(), 16)
            uuid = f"{h:08x}-0000-0000-0000-{h&0xffffffffffff:012x}"
            lines.append(
                f"{p:<12} {fs:<9} 546 MiB   2026-07-01 10:00  /dev/stratis/1/{p}/{fs}  {uuid}"
            )
            total += 1

    if total == 0:
        stdout = "Pool Name    Name      Used      Created            Device                   UUID\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"No Stratis filesystems found{' in pool ' + pool if pool else ''}.",
        )

    stdout = "\n".join(lines) + "\n"
    scope = f" in pool '{pool}'" if pool else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {total} Stratis filesystem(s){scope}.",
    )


def _sim_filesystem_create(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool", "datapool")
    filesystem = args.get("filesystem", "newfs")

    if _name_is_bad(pool):
        stderr = f"stratis: error: Pool '{pool}' not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create filesystem '{filesystem}'; Stratis pool '{pool}' not found.",
        )

    if _name_is_bad(filesystem):
        stderr = f"stratis: error: Filesystem name '{filesystem}' is invalid or already exists.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create Stratis filesystem '{filesystem}' in pool '{pool}'.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Stratis filesystem '{filesystem}' created in pool '{pool}'.",
    )


def _sim_filesystem_snapshot(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool", "datapool")
    filesystem = args.get("filesystem", "rootfs")
    snapshot = args.get("snapshot", "rootfs-snap1")

    if _name_is_bad(pool):
        stderr = f"stratis: error: Pool '{pool}' not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create snapshot; Stratis pool '{pool}' not found.",
        )

    if _name_is_bad(filesystem):
        stderr = f"stratis: error: Filesystem '{filesystem}' not found in pool '{pool}'.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create snapshot; filesystem '{filesystem}' not found in pool '{pool}'.",
        )

    if _name_is_bad(snapshot):
        stderr = f"stratis: error: Snapshot name '{snapshot}' is invalid or already exists.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create snapshot '{snapshot}' from '{filesystem}' in pool '{pool}'.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Snapshot '{snapshot}' created from filesystem '{filesystem}' in pool '{pool}'.",
    )


def _sim_filesystem_destroy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pool = args.get("pool", "datapool")
    filesystem = args.get("filesystem", "rootfs")

    if _name_is_bad(pool):
        stderr = f"stratis: error: Pool '{pool}' not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to destroy filesystem; Stratis pool '{pool}' not found.",
        )

    if _name_is_bad(filesystem):
        stderr = f"stratis: error: Filesystem '{filesystem}' not found in pool '{pool}'.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to destroy filesystem '{filesystem}'; it was not found in pool '{pool}'.",
        )

    # Hash-based scatter: occasionally simulate a mounted filesystem
    h = int(hashlib.md5((pool + filesystem + "destroy").encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = (
            f"stratis: error: Filesystem '{filesystem}' in pool '{pool}' is mounted; "
            "unmount it before destroying.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to destroy filesystem '{filesystem}' in pool '{pool}'; the filesystem is still mounted.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Stratis filesystem '{filesystem}' in pool '{pool}' destroyed; data has been removed.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "pool-list": _sim_pool_list,
    "pool-create": _sim_pool_create,
    "pool-destroy": _sim_pool_destroy,
    "filesystem-list": _sim_filesystem_list,
    "filesystem-create": _sim_filesystem_create,
    "filesystem-snapshot": _sim_filesystem_snapshot,
    "filesystem-destroy": _sim_filesystem_destroy,
}


def simulate_stratis(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'stratis' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; one of the real ops in core/tools/stratis.py.
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — snapshot_text str or profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_stratis: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
