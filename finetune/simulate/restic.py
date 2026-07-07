"""finetune/simulate/restic.py — Rocky Linux 9 output simulator for the 'restic' tool.

Public API
----------
simulate_restic(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real ops declared in core/tools/restic.py
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string from make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Output mirrors real restic v0.16.x output on Rocky Linux 9.
* Failure branches: missing/unreadable repository (exit 1), snapshot not found
  (exit 1), permission denied (exit 1 with AVC-like stderr), binary not found
  (exit 127).
* Deterministic scatter via hash-based branch selection for variety.

I2 compliance
-------------
All summary strings are I2-clean.  No AI/LLM/model/agent language appears.

INV-read-only-core: imports NOTHING from core/ and NOTHING from finetune.coreimports.
The 4-key dict mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic log output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _repo_available(repo: str, ctx: Any) -> bool:
    """Decide whether the named repo path is reachable in the given context."""
    lower = repo.lower() if repo else ""
    for tok in ("missing", "broken", "invalid", "notfound", "noexist", "bogus"):
        if tok in lower:
            return False
    # Hash-based ~12% failure scatter for unnamed/generic repo paths
    key = (repo or "default").encode()
    h = int(hashlib.md5(key).hexdigest(), 16)
    return h % 9 != 0


def _snapshot_exists(snapshot_id: str) -> bool:
    """Return True for plausible snapshot IDs; False for obvious bad ones."""
    lower = snapshot_id.lower()
    for tok in ("notfound", "missing", "bad", "invalid", "bogus", "none"):
        if tok in lower:
            return False
    # Must look like a hex string of reasonable length
    if len(snapshot_id) < 4:
        return False
    return True


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


def _fake_repo_id(repo: str) -> str:
    """Derive a deterministic fake repository ID from the repo path."""
    h = hashlib.md5((repo or "default").encode()).hexdigest()
    return h[:8]


def _fake_snapshot_id(seed: str) -> str:
    h = hashlib.md5(seed.encode()).hexdigest()
    return h[:8]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_snapshots(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    repo = args.get("repo") or "/var/backup/restic"
    tag = args.get("tag")
    host_filter = args.get("host") or _hostname(ctx)

    if not _repo_available(repo, ctx):
        stderr = (
            f"Fatal: unable to open config file: "
            f"<{repo}/config>: open {repo}/config: "
            f"no such file or directory\n"
            f"Is there a restic repository at the following location?\n"
            f"{repo}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Repository at '{repo}' could not be opened.",
        )

    repo_id = _fake_repo_id(repo)
    snap1 = _fake_snapshot_id(repo + "snap1")
    snap2 = _fake_snapshot_id(repo + "snap2")
    snap3 = _fake_snapshot_id(repo + "snap3")

    tag_col = tag if tag else ""
    stdout = (
        f"repository {repo_id} opened (version 2, compression level auto)\n"
        f"ID        Time                 Host               Tags        Paths\n"
        f"------------------------------------------------------------------------\n"
        f"{snap1}  2026-07-01 02:00:01  {host_filter:<18} {tag_col:<11} /etc\n"
        f"{snap2}  2026-07-02 02:00:03  {host_filter:<18} {tag_col:<11} /home\n"
        f"{snap3}  2026-07-03 02:00:02  {host_filter:<18} {tag_col:<11} /var/www\n"
        f"------------------------------------------------------------------------\n"
        f"3 snapshots\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found 3 snapshots in repository '{repo}'.",
    )


def _sim_backup(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    path = args.get("path", "/etc")
    repo = args.get("repo") or "/var/backup/restic"
    tag = args.get("tag")

    if not _repo_available(repo, ctx):
        stderr = (
            f"Fatal: unable to open config file: "
            f"<{repo}/config>: open {repo}/config: "
            f"no such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Backup of '{path}' failed: repository '{repo}' could not be opened.",
        )

    # Hash-based failure for bad paths
    lower = path.lower()
    for tok in ("missing", "notfound", "bogus", "invalid"):
        if tok in lower:
            stderr = f"Fatal: lstat {path}: no such file or directory\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"Backup of '{path}' failed: path does not exist.",
            )

    repo_id = _fake_repo_id(repo)
    snap_id = _fake_snapshot_id(repo + path)
    tag_line = f"Tags:  {tag}\n" if tag else ""
    # Deterministic file count from path hash
    h = int(hashlib.md5(path.encode()).hexdigest(), 16)
    n_files = 100 + (h % 900)
    mb = 10 + (h % 990)

    stdout = (
        f"repository {repo_id} opened (version 2, compression level auto)\n"
        f"no parent snapshot found, will read all files\n"
        f"\n"
        f"Files:        {n_files} new,     0 changed,     0 unmodified\n"
        f"Dirs:            3 new,     0 changed,     0 unmodified\n"
        f"Added to the repository: {mb} MiB ({mb // 2} MiB stored)\n"
        f"\n"
        f"processed {n_files} files, {mb / 1024:.3f} GiB in 0:05\n"
        f"{tag_line}"
        f"snapshot {snap_id} saved\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Backup of '{path}' completed; "
            f"{n_files} files processed, snapshot {snap_id} saved."
        ),
    )


def _sim_restore(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    snapshot_id = args.get("snapshot_id", "latest")
    target = args.get("target", "/tmp/restore")
    repo = args.get("repo") or "/var/backup/restic"

    if not _repo_available(repo, ctx):
        stderr = (
            f"Fatal: unable to open config file: "
            f"<{repo}/config>: open {repo}/config: "
            f"no such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Restore of snapshot '{snapshot_id}' failed: "
                f"repository '{repo}' could not be opened."
            ),
        )

    if not _snapshot_exists(snapshot_id):
        stderr = (
            f"Fatal: \"load <snapshot/{snapshot_id}>\": "
            f"<snapshot/{snapshot_id}> does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Snapshot '{snapshot_id}' was not found in the repository.",
        )

    repo_id = _fake_repo_id(repo)
    h = int(hashlib.md5(snapshot_id.encode()).hexdigest(), 16)
    n_files = 100 + (h % 800)
    mb = 10 + (h % 500)

    stdout = (
        f"repository {repo_id} opened (version 2, compression level auto)\n"
        f"restoring <Snapshot {snapshot_id} of [/etc] at 2026-07-03 02:00:02> to {target}\n"
        f"Summary: Restored {n_files} Files ({mb} MiB) in 0:08\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Snapshot '{snapshot_id}' restored to '{target}' ({n_files} files, {mb} MiB).",
    )


def _sim_forget(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    snapshot_id = args.get("snapshot_id", "")
    repo = args.get("repo") or "/var/backup/restic"

    if not _repo_available(repo, ctx):
        stderr = (
            f"Fatal: unable to open config file: "
            f"<{repo}/config>: open {repo}/config: "
            f"no such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to forget snapshot '{snapshot_id}': repository could not be opened.",
        )

    if not _snapshot_exists(snapshot_id):
        stderr = (
            f"Fatal: \"load <snapshot/{snapshot_id}>\": "
            f"<snapshot/{snapshot_id}> does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Snapshot '{snapshot_id}' was not found; nothing was removed.",
        )

    repo_id = _fake_repo_id(repo)
    stdout = (
        f"repository {repo_id} opened (version 2, compression level auto)\n"
        f"[0:00] 100.00%  1 / 1 snapshots\n"
        f"removed 1 snapshots\n"
        f"\n"
        f"1 snapshots have been removed, running prune is required "
        f"to actually remove the data from the repository\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Snapshot '{snapshot_id}' removed from the repository index. "
            "Run forget_prune to reclaim disk space."
        ),
    )


def _sim_forget_prune(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    repo = args.get("repo") or "/var/backup/restic"
    keep_last = args.get("keep_last")
    host_filter = args.get("host") or _hostname(ctx)

    if not _repo_available(repo, ctx):
        stderr = (
            f"Fatal: unable to open config file: "
            f"<{repo}/config>: open {repo}/config: "
            f"no such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Prune operation failed: repository '{repo}' could not be opened.",
        )

    repo_id = _fake_repo_id(repo)
    keep_line = (
        f"applying policy: keep {keep_last} latest snapshots\n"
        if keep_last else
        "applying policy: keep all snapshots\n"
    )
    h = int(hashlib.md5(repo.encode()).hexdigest(), 16)
    removed = h % 5
    retained = 3 + (h % 4)
    packs_removed = removed * 2

    stdout = (
        f"repository {repo_id} opened (version 2, compression level auto)\n"
        f"Applying Policy: Keep {keep_last or 'all'} snapshots\n"
        f"\n"
        f"keep {retained} snapshots:\n"
        f"ID        Time                 Host               Paths\n"
        f"------------------------------------------------------------------------\n"
        f"{_fake_snapshot_id(repo + 'latest')}  "
        f"2026-07-03 02:00:02  {host_filter:<18} /etc\n"
        f"------------------------------------------------------------------------\n"
        f"{retained} snapshots\n"
        f"\n"
        f"{keep_line}"
        f"remove {removed} snapshots:\n"
        f"[0:00] 100.00%  {removed} / {removed} snapshots\n"
        f"\n"
        f"{removed} snapshots have been removed, running prune\n"
        f"\n"
        f"counting files in repo\n"
        f"building new index for repo\n"
        f"[0:01] 100.00%  {packs_removed * 3} / {packs_removed * 3} packs\n"
        f"\n"
        f"repository contains {packs_removed * 3} packs ({packs_removed * 15} blobs) "
        f"with 512.000 MiB\n"
        f"these blobs were not compressed\n"
        f"\n"
        f"removing {packs_removed} old packs:\n"
        f"[0:00] 100.00%  {packs_removed} / {packs_removed} old packs removed\n"
        f"\n"
        f"Removed snapshots: {removed}\n"
        f"This operation removed {packs_removed} old packs and freed storage.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            f"Pruned {removed} snapshot(s) from '{repo}'; "
            f"{packs_removed} pack file(s) permanently removed."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "snapshots":    _sim_snapshots,
    "backup":       _sim_backup,
    "restore":      _sim_restore,
    "forget":       _sim_forget,
    "forget_prune": _sim_forget_prune,
}


def simulate_restic(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'restic' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 5 real ops declared in
           core/tools/restic.py (snapshots, backup, restore, forget,
           forget_prune).
    args : argument dict (may be {} for all-optional ops; defaults applied).
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
            f"simulate_restic: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
